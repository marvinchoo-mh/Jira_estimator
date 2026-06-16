"""
split_train_test.py

Splits cleaned_jira_issues.csv into a training knowledge base (older 80%)
and a test set (newer 20%) using a time-based split on first_done_at.

Time-based split ensures the estimator is tested realistically: we estimate
future tickets using older historical tickets, so the test set contains
more recent completed tickets.
"""

import csv
from pathlib import Path

from config import DATA_DIR

CLEANED_FILE = DATA_DIR / "cleaned_jira_issues.csv"
TRAIN_FILE = DATA_DIR / "train_knowledge_base.csv"
TEST_FILE = DATA_DIR / "test_tickets.csv"

TRAIN_RATIO = 0.8


def load_cleaned():
    """Load cleaned issues from CSV."""
    rows = []
    with open(CLEANED_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def split_by_time(rows):
    """
    Sort by first_done_at and split: older 80% = train, newer 20% = test.
    This simulates real usage where we estimate new tickets using historical data.
    """
    sorted_rows = sorted(rows, key=lambda r: r["first_done_at"])
    split_index = int(len(sorted_rows) * TRAIN_RATIO)
    train = sorted_rows[:split_index]
    test = sorted_rows[split_index:]
    return train, test


def save_csv(rows, filepath):
    """Save rows to CSV."""
    if not rows:
        print(f"WARNING: No rows to save to {filepath}")
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def print_stats(name, rows):
    """Print summary statistics for a dataset."""
    types = {}
    sp_count = 0
    for r in rows:
        t = r["issue_type"]
        types[t] = types.get(t, 0) + 1
        if r["story_points"] and r["story_points"] != "":
            sp_count += 1

    print(f"\n  {name}: {len(rows)} tickets")
    print(f"    With story points: {sp_count}")
    print(f"    Issue types: {types}")
    if rows:
        print(f"    Date range: {rows[0]['first_done_at'][:10]} to {rows[-1]['first_done_at'][:10]}")


def main():
    print(f"Loading cleaned issues from {CLEANED_FILE}...")
    rows = load_cleaned()
    print(f"Loaded {len(rows)} cleaned issues.")

    train, test = split_by_time(rows)

    print(f"\n--- Train/Test Split ({int(TRAIN_RATIO*100)}/{int((1-TRAIN_RATIO)*100)}) ---")
    print_stats("Train (knowledge base)", train)
    print_stats("Test (evaluation set)", test)

    save_csv(train, TRAIN_FILE)
    save_csv(test, TEST_FILE)

    print(f"\nSaved: {TRAIN_FILE}")
    print(f"Saved: {TEST_FILE}")
    print("\nTrain/test split complete.")


if __name__ == "__main__":
    main()
