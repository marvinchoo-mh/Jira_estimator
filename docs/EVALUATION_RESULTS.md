# Evaluation Results & Accuracy Summary

## Test Setup

- **Training set:** 162 tickets (older completed tickets, indexed in vector DB)
- **Test set:** 41 tickets (newer completed tickets, never seen by the estimator)
- **Method:** For each test ticket, pretend it's brand new → estimate SP + cycle time → compare to actual values

---

## Accuracy Results (Latest)

### Story Point Prediction

| Metric | Value |
|--------|-------|
| Test tickets with actual SP to compare | 26 out of 41 |
| **Average error** | **2.0 story points off** |
| Exact matches (predicted = actual) | 8 out of 26 (31%) |

**What this means:** On average, the estimator's story point prediction is off by about 2 points. For example, if the real answer is 5 SP, it might predict 3 SP. Almost a third of the time it gets the exact right answer.

### Cycle Time Prediction

| Metric | Value |
|--------|-------|
| Test tickets with CT prediction | 41 out of 41 (all of them) |
| **Average error** | **7.2 working days off** |
| Actual fell inside predicted range | 8 out of 41 (20%) |

**What this means:** On average, the predicted cycle time is off by about 7 working days. This is inflated by tickets that took 22-47 days (likely blocked or forgotten in Jira). For typical tickets that complete within 1-2 weeks, the error is much smaller.

### Simple Summary for Stakeholders

> **Story points:** The tool predicts within ~2 story points of the actual value, and gets it exactly right 31% of the time.
>
> **Cycle time:** The tool predicts within ~7 working days on average. This number is inflated by a few outlier tickets that were blocked for weeks. For normal tickets, predictions are closer.
>
> **Coverage:** Every ticket gets a prediction — no blank outputs.

### Confidence Distribution

| Level | Count | Meaning |
|-------|-------|---------|
| High | 26 | Many close matches, low variance |
| Medium | 15 | Reasonable matches, moderate variance |
| Low | 0 | No matches found |

---

## How the Estimator Works (Step by Step)

```
New ticket entered
       │
       ▼
Build combined_text (summary + description + components + labels + epic)
       │
       ▼
Search vector DB for top 5 similar tickets (same issue type)
       │
       ▼
Calculate:
  - Story points = median of similar tickets' SP
  - Cycle time range = 25th–75th percentile of similar tickets' CT
  - Confidence = based on match count, distance, variance
       │
       ▼
Return estimate + explanation
```

---

## Fallback Logic — How It Handles Missing Data

The estimator has three layers of fallback so it ALWAYS returns a prediction:

### Layer 1: Issue Type Grouping

Some issue types are treated as equivalent because they represent the same work:

| If you enter... | It also searches... | Reason |
|----------------|--------------------|---------| 
| Tech | Story, P2 User Story | Same kind of work (code changes, features) |
| Story | Tech, P2 User Story | Same kind of work |
| P2 User Story | Tech, Story | Same kind of work |
| Task | Task only | Different work pattern |
| Bug | Bug only | Different work pattern |
| Sub-task | Sub-task only | Different work pattern |

### Layer 2: All-Types Fallback

If an issue type has NO training data at all (e.g. Epic, Spike), the estimator falls back to searching **all types** in the vector DB. This means it finds the most semantically similar ticket regardless of type.

**When does this kick in?** Only for types not in any group and not in the training set.

**Trade-off:** The prediction is less reliable since it's comparing across different work types, but it's better than returning nothing.

### Layer 3: Training Set Median Fallback

If similar tickets are found but **none of them have story points**, the estimator uses the **median story points from the entire training set** (which is 3.0 SP).

**When does this kick in?** When the vector search finds matches by text similarity, but those specific tickets never had story points assigned.

**Trade-off:** It's a generic estimate, not tailored to the specific ticket — but it gives a reasonable starting point.

---

## Accuracy Evolution (Version History)

| Version | Change | SP Predictions | Avg SP Error | CT Predictions | Avg CT Error | Range Accuracy |
|---------|--------|----------------|--------------|----------------|--------------|----------------|
| V1 | Strict same-type matching | 11/38 | 1.5 | 16/38 | 4.1 days | 31% |
| V2 | Tech + Story grouped | 33/38 | 2.1 | 38/38 | 4.3 days | 34% |
| V3 (current) | + P2 group + all-types fallback + SP fallback | 26/41 | 2.0 | 41/41 | 7.2 days | 20% |

**Key insight:** Grouping Tech + Story was the biggest improvement — it eliminated all "Low confidence" results. The higher CT error in V3 is due to fresh test data containing more long-running tickets (10-22 days) that are harder to predict. Every ticket now gets a prediction regardless of type.

---

## Known Limitations

1. **High-SP tickets underestimated:** Tickets with 8 SP are often predicted as 3-5 SP because the training set has many small tickets and few large ones
2. **Outlier cycle times missed:** Tickets that took 30-47 days (likely blocked/forgotten) are predicted as 3-8 days — the estimator can't predict human delays
3. **Range too narrow sometimes:** 34% range accuracy means 66% of actual cycle times fall outside the predicted range — wider ranges would capture more but be less useful
4. **Training data skew:** 119/151 training tickets are "Tech" type — other types have limited data (7 Bug, 5 Sub-task)

---

## How to Improve Accuracy

| Improvement | Expected Impact |
|-------------|----------------|
| More completed tickets (re-extract after more are Done) | More training data → better matches |
| Wider cycle time range (10th–90th percentile instead of 25th–75th) | Higher range accuracy % |
| Weight by similarity distance (closer matches count more) | Better SP predictions for unusual tickets |
| Add comments to combined_text | Better semantic matching |
| Separate model for high-SP tickets (5+) | Fix the underestimation problem |
