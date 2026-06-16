"""
evaluate_estimator.py

Runs the estimator against all test tickets in data/test_tickets.csv and
measures prediction accuracy. Each test ticket is treated as a new unseen
ticket — the estimator retrieves similar tickets only from the training
knowledge base (which the test tickets were never part of).

Outputs:
  - data/evaluation_results.csv (per-ticket predictions vs actuals)
  - Printed summary metrics (median errors, range accuracy %)
"""

import csv
import statistics

from config import DATA_DIR
from estimate_ticket import estimate_ticket

TEST_FILE = DATA_DIR / "test_tickets.csv"
RESULTS_FILE = DATA_DIR / "evaluation_results.csv"

RESULTS_COLUMNS = [
    "issue_key",
    "issue_type",
    "summary",
    "actual_story_points",
    "predicted_story_points",
    "absolute_story_point_error",
    "actual_cycle_time_working_days",
    "predicted_cycle_time_range",
    "cycle_time_error",
    "actual_cycle_time_inside_predicted_range",
    "confidence",
    "top_similar_tickets",
]


def load_test_tickets():
    """Load test tickets from CSV."""
    rows = []
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def evaluate_single_ticket(ticket):
    """
    Run the estimator on a single test ticket and compare to actuals.
    Returns a result dict for the evaluation CSV.
    """
    # Parse actual values
    actual_sp_raw = ticket.get("story_points", "")
    actual_sp = float(actual_sp_raw) if actual_sp_raw else None

    actual_ct_raw = ticket.get("cycle_time_working_days", "")
    actual_ct = int(actual_ct_raw) if actual_ct_raw else None

    # Run estimator (treating this as a new ticket)
    result = estimate_ticket(
        summary=ticket.get("summary", ""),
        issue_type=ticket.get("issue_type", ""),
        description=ticket.get("description", ""),
        components=ticket.get("component", "").split(";") if ticket.get("component") else None,
        labels=ticket.get("labels", "").split(";") if ticket.get("labels") else None,
        parent_summary=None,
    )

    predicted_sp = result["suggested_story_points"]
    ct_low = result["cycle_time_low"]
    ct_high = result["cycle_time_high"]

    # Calculate story point error
    sp_error = None
    if actual_sp is not None and predicted_sp is not None:
        sp_error = abs(actual_sp - predicted_sp)

    # Calculate cycle time error (distance from actual to nearest range boundary)
    ct_error = None
    inside_range = None
    if actual_ct is not None and ct_low is not None and ct_high is not None:
        if ct_low <= actual_ct <= ct_high:
            ct_error = 0
            inside_range = True
        elif actual_ct < ct_low:
            ct_error = ct_low - actual_ct
            inside_range = False
        else:
            ct_error = actual_ct - ct_high
            inside_range = False

    # Format similar tickets for CSV
    similar_str = "; ".join(
        f"{t['issue_key']}({t.get('story_points', 'N/A')}SP,{t.get('cycle_time_working_days', 'N/A')}d)"
        for t in result["similar_tickets"]
    )

    # Format predicted range
    range_str = f"{ct_low}-{ct_high}" if ct_low is not None else "N/A"

    return {
        "issue_key": ticket["issue_key"],
        "issue_type": ticket["issue_type"],
        "summary": ticket.get("summary", "")[:80],
        "actual_story_points": actual_sp,
        "predicted_story_points": predicted_sp,
        "absolute_story_point_error": sp_error,
        "actual_cycle_time_working_days": actual_ct,
        "predicted_cycle_time_range": range_str,
        "cycle_time_error": ct_error,
        "actual_cycle_time_inside_predicted_range": inside_range,
        "confidence": result["confidence"],
        "top_similar_tickets": similar_str,
    }


def save_results(results):
    """Save evaluation results to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


def print_metrics(results):
    """Print summary evaluation metrics."""
    # Story point errors (only where both actual and predicted exist)
    sp_errors = [r["absolute_story_point_error"] for r in results
                 if r["absolute_story_point_error"] is not None]

    # Cycle time errors
    ct_errors = [r["cycle_time_error"] for r in results
                 if r["cycle_time_error"] is not None]

    # Range accuracy
    inside_count = sum(1 for r in results
                       if r["actual_cycle_time_inside_predicted_range"] is True)
    range_total = sum(1 for r in results
                      if r["actual_cycle_time_inside_predicted_range"] is not None)

    print(f"\n{'=' * 60}")
    print("EVALUATION METRICS")
    print(f"{'=' * 60}")
    print(f"\nTest tickets evaluated: {len(results)}")

    print(f"\n--- Story Point Accuracy ---")
    if sp_errors:
        print(f"  Tickets with SP prediction: {len(sp_errors)}")
        print(f"  Median absolute error: {statistics.median(sp_errors):.1f}")
        print(f"  Mean absolute error: {statistics.mean(sp_errors):.1f}")
        print(f"  Exact matches (error=0): {sum(1 for e in sp_errors if e == 0)}/{len(sp_errors)}")
    else:
        print("  No story point predictions available.")

    print(f"\n--- Cycle Time Accuracy ---")
    if ct_errors:
        print(f"  Tickets with CT prediction: {len(ct_errors)}")
        print(f"  Median absolute error: {statistics.median(ct_errors):.1f} days")
        print(f"  Mean absolute error: {statistics.mean(ct_errors):.1f} days")
    else:
        print("  No cycle time predictions available.")

    if range_total > 0:
        pct = (inside_count / range_total) * 100
        print(f"\n--- Range Prediction ---")
        print(f"  Actual CT inside predicted range: {inside_count}/{range_total} ({pct:.0f}%)")

    # Confidence distribution
    conf_dist = {}
    for r in results:
        c = r["confidence"]
        conf_dist[c] = conf_dist.get(c, 0) + 1
    print(f"\n--- Confidence Distribution ---")
    for c, count in sorted(conf_dist.items()):
        print(f"  {c}: {count}")


def main():
    print(f"Loading test tickets from {TEST_FILE}...")
    test_tickets = load_test_tickets()
    print(f"Loaded {len(test_tickets)} test tickets.\n")

    print("Running estimator on each test ticket...")
    results = []
    for i, ticket in enumerate(test_tickets, 1):
        result = evaluate_single_ticket(ticket)
        results.append(result)
        print(f"  [{i}/{len(test_tickets)}] {result['issue_key']} — "
              f"SP: {result['actual_story_points']}→{result['predicted_story_points']}, "
              f"CT: {result['actual_cycle_time_working_days']}d→{result['predicted_cycle_time_range']}, "
              f"Conf: {result['confidence']}")

    save_results(results)
    print(f"\nResults saved to {RESULTS_FILE}")

    print_metrics(results)


if __name__ == "__main__":
    main()
