"""
jira_extract.py

Extracts Jira issues from board 520 (TNR PP - Permit Processing) and saves
the raw Jira issue data to data/raw_jira_issues.json.

Uses the Jira Agile REST API (/rest/agile/1.0/board/{boardId}/issue) which
returns only issues visible on the specific board, with full fields and
changelog in a single request.

This script does not clean the data or calculate estimates. It only handles
raw extraction from Jira.
"""

import json
import time
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    JIRA_SITE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_BOARD_ID,
    DATA_DIR,
    RAW_JIRA_FILE,
)

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json"}
MAX_RESULTS = 50
REQUEST_DELAY_SECONDS = 1.0
SAVE_EVERY = 200


def create_session():
    """Create a requests session with retry logic for network errors."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.auth = AUTH
    session.headers.update(HEADERS)
    return session


def discover_story_points_field(session):
    """
    Query Jira fields metadata to find the story points custom field ID.
    Returns the field ID string (e.g. 'customfield_10274') or None if not found.
    """
    url = f"{JIRA_SITE_URL}/rest/api/3/field"
    response = session.get(url)
    response.raise_for_status()

    fields = response.json()
    for field in fields:
        name = field.get("name", "").lower()
        if "story point" in name and "estimate" not in name:
            print(f"Discovered story points field: {field['name']} -> {field['id']}")
            return field["id"]

    for field in fields:
        if field.get("id") == "story_points" or field.get("key") == "story_points":
            print(f"Discovered story points field (fallback): {field['id']}")
            return field["id"]

    print("WARNING: Could not discover story points field. Story points will be null.")
    return None


def extract_issues(session, story_points_field_id):
    """
    Extract all issues from board 520 using the Agile REST API.
    Returns full fields and changelog in one paginated call.
    """
    start_at = 0
    all_issues = []
    total = None

    while True:
        url = f"{JIRA_SITE_URL}/rest/agile/1.0/board/{JIRA_BOARD_ID}/issue"
        params = {
            "startAt": start_at,
            "maxResults": MAX_RESULTS,
            "expand": "changelog",
        }

        response = session.get(url, params=params)
        if not response.ok:
            print(f"Error {response.status_code}: {response.text[:200]}")
            response.raise_for_status()

        data = response.json()

        if total is None:
            total = data["total"]
            print(f"Total issues on board {JIRA_BOARD_ID}: {total}")

        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            extracted = extract_issue_fields(issue, story_points_field_id)
            all_issues.append(extracted)

        start_at += len(issues)
        print(f"Fetched {start_at}/{total} issues...")

        # Save incrementally
        if start_at % SAVE_EVERY == 0:
            save_to_file(all_issues)

        if start_at >= total:
            break

        time.sleep(REQUEST_DELAY_SECONDS)

    return all_issues


def extract_issue_fields(issue, story_points_field_id):
    """Extract relevant fields from a single Jira issue."""
    fields = issue.get("fields", {})

    story_points = None
    if story_points_field_id:
        story_points = fields.get(story_points_field_id)

    components = [c.get("name", "") for c in (fields.get("components") or [])]
    labels = fields.get("labels") or []

    parent = fields.get("parent")
    parent_key = parent.get("key") if parent else None
    parent_summary = None
    if parent and parent.get("fields"):
        parent_summary = parent["fields"].get("summary")

    sprint = fields.get("sprint")
    if sprint and isinstance(sprint, dict):
        sprint_name = sprint.get("name")
    elif sprint and isinstance(sprint, list) and len(sprint) > 0:
        sprint_name = sprint[-1].get("name") if isinstance(sprint[-1], dict) else str(sprint[-1])
    else:
        sprint_name = None

    resolution = fields.get("resolution")
    resolution_name = resolution.get("name") if resolution else None

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


def save_to_file(issues):
    """Save current issues list to the output JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_JIRA_FILE, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2, ensure_ascii=False, default=str)


def main():
    print(f"Extracting issues from board {JIRA_BOARD_ID} at {JIRA_SITE_URL}...")
    print()

    session = create_session()

    story_points_field_id = discover_story_points_field(session)
    print()

    issues = extract_issues(session, story_points_field_id)

    save_to_file(issues)
    print()
    print(f"Saved {len(issues)} issues to {RAW_JIRA_FILE}")
    print("Phase 1 extraction complete.")


if __name__ == "__main__":
    main()
