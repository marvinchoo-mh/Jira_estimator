"""
clean_jira_data.py

Cleans the raw Jira data from data/raw_jira_issues.json, calculates cycle time,
creates combined_text for semantic search, and saves cleaned_jira_issues.csv.

This script does not build embeddings or estimate anything. It only handles
data cleaning and derived field creation.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR, RAW_JIRA_FILE

CLEANED_FILE = DATA_DIR / "cleaned_jira_issues.csv"

# ============================================================================
# CYCLE TIME STATUS MATCHING
#
# Board 520 (TNR PP) uses several "in progress" status variants:
#   - "Dev In Progress"    (most common — primary dev work status)
#   - "In Progress"        (legacy or alternate workflow)
#   - "In Progress / Dev"  (alternate naming seen in changelog)
#
# We match ANY status containing "in progress" (case-insensitive) so that
# cycle time captures the first moment work actually began, regardless of
# which specific workflow variant was used for that ticket.
#
# Cycle time = first transition TO an "in progress" status → first transition TO "Done"
# ============================================================================

# Resolutions that mean the ticket was NOT actually completed
EXCLUDED_RESOLUTIONS = {
    "cancelled",
    "duplicate",
    "rejected",
    "won't do",
    "no longer required",
}

# Maximum cycle time in working days before we consider it an outlier
# (tickets left open for months because someone forgot to update Jira)
MAX_CYCLE_TIME_WORKING_DAYS = 90

CSV_COLUMNS = [
    "issue_key",
    "issue_type",
    "summary",
    "description",
    "combined_text",
    "story_points",
    "first_in_progress_at",
    "first_done_at",
    "cycle_time_working_days",
    "component",
    "labels",
    "epic_key",
    "parent_key",
    "sprint",
    "resolution",
    "status_path",
]


def is_in_progress_status(status_name):
    """
    Check if a status represents "in progress" work.
    Matches case-insensitively against any status containing "in progress".
    Known matches from board 520 data:
      - "Dev In Progress"
      - "In Progress"
      - "In Progress / Dev"
    """
    return "in progress" in status_name.lower()


def is_done_status(status_name):
    """Check if a status represents completed work (only 'Done', not 'Closed')."""
    return status_name.strip().lower() == "done"


def get_sorted_changelog(issue):
    """
    Return changelog entries sorted by date ascending (oldest first).
    Raw data may have them in reverse chronological order.
    """
    changelog = issue.get("changelog", [])
    return sorted(changelog, key=lambda x: x.get("date", ""))


def find_first_transition_to(changelog, status_checker):
    """
    Find the first changelog entry where to_status matches the checker function.
    Returns the timestamp string or None.
    """
    for entry in changelog:
        to_status = entry.get("to_status", "")
        if to_status and status_checker(to_status):
            return entry["date"]
    return None


def parse_jira_timestamp(ts):
    """
    Parse Jira timestamp strings like '2026-04-10T15:16:09.209+0800'.
    Jira uses +0800 instead of +08:00, which Python's fromisoformat doesn't handle
    in older versions.
    """
    ts = ts.replace("Z", "+00:00")
    # Fix timezone offset: +0800 -> +08:00
    if len(ts) > 5 and ts[-5] in ("+", "-") and ":" not in ts[-5:]:
        ts = ts[:-2] + ":" + ts[-2:]
    return datetime.fromisoformat(ts)


def calculate_working_days(start_str, end_str):
    """
    Calculate the number of working days (Mon-Fri) between two ISO timestamps.
    Excludes weekends. Does not account for public holidays (MVP simplification).
    """
    start = parse_jira_timestamp(start_str)
    end = parse_jira_timestamp(end_str)

    # If Done came before In Progress (bad data / re-opened ticket), return -1 to flag it
    if end <= start:
        return -1

    working_days = 0
    current = start.date()
    end_date = end.date()

    while current <= end_date:
        if current.weekday() < 5:  # Monday=0 to Friday=4
            working_days += 1
        current += timedelta(days=1)

    # If started and finished same day, that's 1 working day
    return max(working_days, 1)


def build_status_path(changelog):
    """Build an ordered string showing the status transitions: Open -> Dev In Progress -> Done"""
    if not changelog:
        return ""
    statuses = []
    # Start with the first from_status
    if changelog[0].get("from_status"):
        statuses.append(changelog[0]["from_status"])
    for entry in changelog:
        if entry.get("to_status"):
            statuses.append(entry["to_status"])
    return " -> ".join(statuses)


def build_combined_text(issue):
    """
    Create combined_text for semantic search.
    Combines: issue_type, summary, description, components, labels, parent_summary.
    This gives the embedding model richer context for finding similar tickets.
    """
    parts = []

    issue_type = issue.get("issue_type", "")
    if issue_type:
        parts.append(f"Issue Type: {issue_type}.")

    summary = issue.get("summary", "")
    if summary:
        parts.append(f"Summary: {summary}.")

    description = issue.get("description", "")
    if description:
        # Truncate very long descriptions to keep embeddings focused
        desc_text = description[:1000] if len(description) > 1000 else description
        parts.append(f"Description: {desc_text}.")

    components = issue.get("components", [])
    if components:
        parts.append(f"Component: {', '.join(components)}.")

    labels = issue.get("labels", [])
    if labels:
        parts.append(f"Labels: {', '.join(labels)}.")

    parent_summary = issue.get("parent_summary", "")
    if parent_summary:
        parts.append(f"Epic/Parent: {parent_summary}.")

    return " ".join(parts)


def clean_issues():
    """Main cleaning pipeline."""
    print(f"Loading raw issues from {RAW_JIRA_FILE}...")
    with open(RAW_JIRA_FILE, "r", encoding="utf-8") as f:
        raw_issues = json.load(f)
    print(f"Loaded {len(raw_issues)} raw issues.")

    cleaned = []
    stats = {
        "total": len(raw_issues),
        "not_done": 0,
        "excluded_resolution": 0,
        "no_in_progress": 0,
        "no_done_transition": 0,
        "outlier": 0,
        "kept": 0,
    }

    for issue in raw_issues:
        # Filter 1: Keep only tickets with current status "Done"
        if issue.get("status", "").strip().lower() != "done":
            stats["not_done"] += 1
            continue

        # Filter 2: Exclude cancelled/duplicate/rejected resolutions
        resolution = (issue.get("resolution") or "").strip().lower()
        if resolution in EXCLUDED_RESOLUTIONS:
            stats["excluded_resolution"] += 1
            continue

        # Sort changelog chronologically
        changelog = get_sorted_changelog(issue)

        # Find first "in progress" and first "done" transitions
        first_in_progress = find_first_transition_to(changelog, is_in_progress_status)
        first_done = find_first_transition_to(changelog, is_done_status)

        # Filter 3: Must have both timestamps
        if not first_in_progress:
            stats["no_in_progress"] += 1
            continue
        if not first_done:
            stats["no_done_transition"] += 1
            continue

        # Calculate cycle time in working days
        cycle_time = calculate_working_days(first_in_progress, first_done)

        # Filter 4: Remove invalid cycle times (Done before In Progress) and extreme outliers
        if cycle_time < 1:
            stats["outlier"] += 1
            continue
        if cycle_time > MAX_CYCLE_TIME_WORKING_DAYS:
            stats["outlier"] += 1
            continue

        # Build derived fields
        combined_text = build_combined_text(issue)
        status_path = build_status_path(changelog)
        labels_str = ";".join(issue.get("labels", []))
        component_str = ";".join(issue.get("components", []))

        cleaned.append({
            "issue_key": issue["key"],
            "issue_type": issue.get("issue_type", ""),
            "summary": issue.get("summary", ""),
            "description": issue.get("description", ""),
            "combined_text": combined_text,
            "story_points": issue.get("story_points"),
            "first_in_progress_at": first_in_progress,
            "first_done_at": first_done,
            "cycle_time_working_days": cycle_time,
            "component": component_str,
            "labels": labels_str,
            "epic_key": issue.get("parent_key", ""),
            "parent_key": issue.get("parent_key", ""),
            "sprint": issue.get("sprint", ""),
            "resolution": issue.get("resolution", ""),
            "status_path": status_path,
        })
        stats["kept"] += 1

    return cleaned, stats


def save_csv(cleaned):
    """Save cleaned issues to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CLEANED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned)
    print(f"Saved {len(cleaned)} cleaned issues to {CLEANED_FILE}")


def main():
    cleaned, stats = clean_issues()

    print(f"\n--- Cleaning Summary ---")
    print(f"Total raw issues:          {stats['total']}")
    print(f"Excluded (not Done):       {stats['not_done']}")
    print(f"Excluded (resolution):     {stats['excluded_resolution']}")
    print(f"Excluded (no In Progress): {stats['no_in_progress']}")
    print(f"Excluded (no Done trans.): {stats['no_done_transition']}")
    print(f"Excluded (outlier >90d):   {stats['outlier']}")
    print(f"Kept (cleaned):            {stats['kept']}")

    if cleaned:
        # Summary stats
        cycle_times = [r["cycle_time_working_days"] for r in cleaned]
        sp_values = [r["story_points"] for r in cleaned if r["story_points"] is not None]
        types = {}
        for r in cleaned:
            t = r["issue_type"]
            types[t] = types.get(t, 0) + 1

        print(f"\n--- Data Stats ---")
        print(f"Cycle time range: {min(cycle_times)} - {max(cycle_times)} working days")
        print(f"Median cycle time: {sorted(cycle_times)[len(cycle_times)//2]} working days")
        print(f"Issues with story points: {len(sp_values)}/{len(cleaned)}")
        print(f"Issue types: {types}")

    save_csv(cleaned)
    print("\nPhase 2 cleaning complete.")


if __name__ == "__main__":
    main()
