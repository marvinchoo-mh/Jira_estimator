"""
jira_extract.py

Extracts Jira issues from the TNR project (board 520) and saves the raw
Jira issue data to data/raw_jira_issues.json.

This script does not clean the data or calculate estimates. It only handles
raw extraction from Jira.
"""

import json
import time
import requests
from requests.auth import HTTPBasicAuth

from config import (
    JIRA_SITE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_PROJECT_KEY,
    DATA_DIR,
    RAW_JIRA_FILE,
)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json"}
MAX_RESULTS = 100
REQUEST_DELAY_SECONDS = 0.5


def discover_story_points_field():
    """
    Query Jira fields metadata to find the story points custom field ID.
    Returns the field ID string (e.g. 'customfield_10016') or None if not found.
    """
    url = f"{JIRA_SITE_URL}/rest/api/3/field"
    response = requests.get(url, headers=HEADERS, auth=AUTH)
    response.raise_for_status()

    fields = response.json()
    for field in fields:
        name = field.get("name", "").lower()
        if "story point" in name and "estimate" not in name:
            print(f"Discovered story points field: {field['name']} -> {field['id']}")
            return field["id"]

    # Fallback: try common field IDs
    for field in fields:
        if field.get("id") == "story_points" or field.get("key") == "story_points":
            print(f"Discovered story points field (fallback): {field['id']}")
            return field["id"]

    print("WARNING: Could not discover story points field. Story points will be null.")
    return None


def extract_issues(story_points_field_id):
    """
    Extract all issues from the configured Jira project using JQL search
    with pagination. Includes changelog for status transition history.
    """
    jql = f"project = {JIRA_PROJECT_KEY} ORDER BY created ASC"
    start_at = 0
    all_issues = []
    total = None

    while True:
        url = f"{JIRA_SITE_URL}/rest/api/3/search"
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": MAX_RESULTS,
            "expand": "changelog",
            "fields": "*all",
        }

        response = requests.get(url, headers=HEADERS, auth=AUTH, params=params)
        response.raise_for_status()
        data = response.json()

        if total is None:
            total = data["total"]
            print(f"Total issues to extract: {total}")

        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            extracted = extract_issue_fields(issue, story_points_field_id)
            all_issues.append(extracted)

        start_at += len(issues)
        print(f"Fetched {start_at}/{total} issues...")

        if start_at >= total:
            break

        time.sleep(REQUEST_DELAY_SECONDS)

    return all_issues


def extract_issue_fields(issue, story_points_field_id):
    """Extract relevant fields from a single Jira issue."""
    fields = issue.get("fields", {})

    # Story points from discovered custom field
    story_points = None
    if story_points_field_id:
        story_points = fields.get(story_points_field_id)

    # Components
    components = [c.get("name", "") for c in (fields.get("components") or [])]

    # Labels
    labels = fields.get("labels") or []

    # Parent / Epic
    parent = fields.get("parent")
    parent_key = parent.get("key") if parent else None
    parent_summary = None
    if parent and parent.get("fields"):
        parent_summary = parent["fields"].get("summary")

    # Sprint (may be in a custom field, grab from fields directly)
    sprint = fields.get("sprint")
    if sprint and isinstance(sprint, dict):
        sprint_name = sprint.get("name")
    elif sprint and isinstance(sprint, list) and len(sprint) > 0:
        sprint_name = sprint[-1].get("name") if isinstance(sprint[-1], dict) else str(sprint[-1])
    else:
        sprint_name = None

    # Resolution
    resolution = fields.get("resolution")
    resolution_name = resolution.get("name") if resolution else None

    # Changelog
    changelog_entries = extract_changelog(issue)

    return {
        "key": issue.get("key"),
        "issue_type": fields.get("issuetype", {}).get("name"),
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "status": fields.get("status", {}).get("name"),
        "resolution": resolution_name,
        "story_points": story_points,
        "components": components,
        "labels": labels,
        "parent_key": parent_key,
        "parent_summary": parent_summary,
        "sprint": sprint_name,
        "created": fields.get("created"),
        "changelog": changelog_entries,
    }


def extract_changelog(issue):
    """Extract status transition history from the issue changelog."""
    changelog = issue.get("changelog", {})
    histories = changelog.get("histories", [])
    transitions = []

    for history in histories:
        created = history.get("created")
        for item in history.get("items", []):
            if item.get("field") == "status":
                transitions.append({
                    "date": created,
                    "from_status": item.get("fromString"),
                    "to_status": item.get("toString"),
                })

    return transitions


def main():
    print(f"Extracting issues from {JIRA_SITE_URL}, project {JIRA_PROJECT_KEY}...")
    print()

    # Step 1: Discover story points field
    story_points_field_id = discover_story_points_field()
    print()

    # Step 2: Extract all issues
    issues = extract_issues(story_points_field_id)
    print()

    # Step 3: Save to JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_JIRA_FILE, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2, ensure_ascii=False, default=str)

    print(f"Saved {len(issues)} issues to {RAW_JIRA_FILE}")
    print("Phase 1 extraction complete.")


if __name__ == "__main__":
    main()
