"""
estimate_ticket.py

Takes a new Jira ticket's details, finds similar historical tickets via
vector search, and calculates:
  - Suggested story points (median from similar tickets)
  - Estimated cycle time range (25th–75th percentile)
  - Confidence level (High/Medium/Low)

This script does not use an LLM. It calculates estimates purely from
the retrieved similar tickets' actual data.
"""

import csv
import statistics

from build_vector_index import search_similar_tickets
from config import DATA_DIR

TRAIN_FILE = DATA_DIR / "train_knowledge_base.csv"


def _get_training_fallback_stats():
    """
    Calculate fallback stats from the full training set.
    Used when similar tickets are found but none have story points.
    """
    sp_values = []
    ct_values = []
    with open(TRAIN_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("story_points"):
                sp_values.append(float(row["story_points"]))
            if row.get("cycle_time_working_days"):
                ct_values.append(int(row["cycle_time_working_days"]))
    return {
        "median_sp": statistics.median(sp_values) if sp_values else None,
        "median_ct": statistics.median(ct_values) if ct_values else None,
    }


def build_combined_text(issue_type, summary, description=None, components=None,
                        labels=None, parent_summary=None):
    """
    Build combined_text in the same format used during indexing.
    Must match the format in clean_jira_data.py so embeddings are comparable.
    """
    parts = []

    if issue_type:
        parts.append(f"Issue Type: {issue_type}.")
    if summary:
        parts.append(f"Summary: {summary}.")
    if description:
        desc_text = description[:1000] if len(description) > 1000 else description
        parts.append(f"Description: {desc_text}.")
    if components:
        comp_str = ", ".join(components) if isinstance(components, list) else components
        parts.append(f"Component: {comp_str}.")
    if labels:
        label_str = ", ".join(labels) if isinstance(labels, list) else labels
        parts.append(f"Labels: {label_str}.")
    if parent_summary:
        parts.append(f"Epic/Parent: {parent_summary}.")

    return " ".join(parts)


def calculate_confidence(similar_tickets, sp_values, ct_values):
    """
    Determine confidence level based on:
    - Number of similar tickets found
    - Average similarity distance (lower = more similar)
    - Variance in story points
    """
    n = len(similar_tickets)
    if n == 0:
        return "Low"

    avg_distance = sum(t["distance"] for t in similar_tickets) / n

    # High confidence: many close matches with low variance
    if n >= 3 and avg_distance < 0.3:
        if sp_values and statistics.pstdev(sp_values) <= 1.0:
            return "High"
        if not sp_values and ct_values and statistics.pstdev(ct_values) <= 2.0:
            return "High"

    # Medium confidence: some matches, reasonable distance
    if n >= 2 and avg_distance < 0.5:
        return "Medium"

    return "Low"


def estimate_ticket(summary, issue_type, description=None, components=None,
                    labels=None, parent_summary=None, top_k=5):
    """
    Estimate story points and cycle time for a new ticket.

    Args:
        summary: Ticket summary/title
        issue_type: "Story", "Task", "Bug", "Sub-task", or "Tech"
        description: Ticket description text (optional)
        components: List of component names (optional)
        labels: List of labels (optional)
        parent_summary: Parent/epic title (optional)
        top_k: Number of similar tickets to retrieve

    Returns:
        Dict with: suggested_story_points, cycle_time_low, cycle_time_high,
        confidence, similar_tickets
    """
    combined_text = build_combined_text(
        issue_type=issue_type,
        summary=summary,
        description=description,
        components=components,
        labels=labels,
        parent_summary=parent_summary,
    )

    similar_tickets = search_similar_tickets(combined_text, issue_type, top_k=top_k)

    if not similar_tickets:
        return {
            "suggested_story_points": None,
            "cycle_time_low": None,
            "cycle_time_high": None,
            "confidence": "Low",
            "similar_tickets": [],
        }

    # Story points: median of similar tickets that have valid story points
    sp_values = [t["story_points"] for t in similar_tickets if t["story_points"] is not None]
    if sp_values:
        suggested_sp = statistics.median(sp_values)
    else:
        # Fallback: use median SP from entire training set
        fallback = _get_training_fallback_stats()
        suggested_sp = fallback["median_sp"]

    # Cycle time: 25th–75th percentile range
    ct_values = [t["cycle_time_working_days"] for t in similar_tickets if t["cycle_time_working_days"] is not None]
    if ct_values:
        ct_sorted = sorted(ct_values)
        n = len(ct_sorted)
        low_idx = max(0, n // 4)
        high_idx = min(n - 1, (3 * n) // 4)
        cycle_time_low = ct_sorted[low_idx]
        cycle_time_high = ct_sorted[high_idx]
        # Ensure range is at least 1 day wide
        if cycle_time_low == cycle_time_high and n > 1:
            cycle_time_high = cycle_time_low + 1
    else:
        cycle_time_low = None
        cycle_time_high = None

    confidence = calculate_confidence(similar_tickets, sp_values, ct_values)

    return {
        "suggested_story_points": suggested_sp,
        "cycle_time_low": cycle_time_low,
        "cycle_time_high": cycle_time_high,
        "confidence": confidence,
        "similar_tickets": similar_tickets,
    }


def print_estimate(result, summary):
    """Print a formatted estimate for display."""
    print(f"Ticket: \"{summary}\"")
    print()

    sp = result["suggested_story_points"]
    if sp is not None:
        print(f"Suggested story points: {sp:.0f}")
    else:
        print("Suggested story points: N/A (no similar tickets have story points)")

    low = result["cycle_time_low"]
    high = result["cycle_time_high"]
    if low is not None:
        print(f"Estimated cycle time: {low}–{high} working days")
    else:
        print("Estimated cycle time: N/A")

    print(f"Confidence: {result['confidence']}")

    print(f"\nTop similar tickets:")
    for i, t in enumerate(result["similar_tickets"], 1):
        sp_str = f"{t['story_points']:.0f} SP" if t["story_points"] else "no SP"
        ct_str = f"{t['cycle_time_working_days']}d" if t["cycle_time_working_days"] else "no CT"
        print(f"  {i}. {t['issue_key']} — {sp_str}, {ct_str} (distance: {t['distance']:.3f})")


def main():
    """Demo: estimate a sample ticket."""
    print("=" * 60)
    print("JIRA TICKET ESTIMATOR — Demo")
    print("=" * 60)
    print()

    result = estimate_ticket(
        summary="Add validation rule for permit reject code REJ021",
        issue_type="Tech",
        description="Implement a new Kogito validation rule for reject code REJ021 in permit processing",
        components=["Permit Processing"],
        labels=["Kogito", "validation"],
    )
    print_estimate(result, "Add validation rule for permit reject code REJ021")


if __name__ == "__main__":
    main()
