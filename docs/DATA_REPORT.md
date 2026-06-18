# Data Extraction & Cleaning Report

## Ticket Counts — Before and After Cleaning

### Raw Extraction (Board 520 via Agile API)
**Total extracted: 1,887 tickets**

Status breakdown of all raw tickets:
| Status | Count |
|--------|-------|
| Open | ~990 |
| Closed | ~326 |
| Done | ~283 |
| Ready for Dev | ~166 |
| Accepted | ~103 |
| Dev In Progress | ~17 |
| Other (Reviewed, READY FOR TEST, Development Done) | ~2 |

### Cleaning Pipeline — Step by Step Removal

| Step | Rule | Removed | Remaining |
|------|------|---------|-----------|
| Start | Raw tickets from board 520 | — | 1,887 |
| 1 | Status is not "Done" (only keep completed tickets) | 1,604 | 283 |
| 2 | Excluded resolution (Cancelled, Duplicate, Rejected, Won't Do, No Longer Required) | 0 | 283 |
| 3 | No "In Progress" transition in changelog (ticket jumped straight to Done without active work) | 74 | 209 |
| 4 | No "Done" transition in changelog | 0 | 209 |
| 5 | Outlier: cycle time > 90 working days OR Done came before In Progress (bad data) | 6 | **203** |

### Final Cleaned Dataset
| Metric | Value |
|--------|-------|
| Total cleaned tickets | 203 |
| With story points | 165 |
| Without story points | 38 |
| Cycle time range | 1 – 83 working days |
| Median cycle time | 5 working days |

### Issue Type Breakdown (Cleaned)
| Issue Type | Count |
|-----------|-------|
| Tech | 128 |
| Story | 31 |
| Task | 22 |
| Sub-task | 15 |
| Bug | 7 |

### Train/Test Split (80/20 time-based)
| Set | Count | Date Range | With Story Points |
|-----|-------|------------|-------------------|
| Train (knowledge base) | 162 | 2024-12-20 to 2026-05-14 | 139 |
| Test (evaluation) | 41 | 2026-05-15 to 2026-06-18 | 26 |

---

## Fields Extracted — What We Take and Why

Jira provides **578 fields** per ticket (47 standard + 531 custom fields). We extract only **14 fields**. Here's the justification:

### Fields We Extract

| Field | Why We Need It |
|-------|---------------|
| `key` | Unique ticket identifier (e.g. TNR-16381). Needed to trace predictions back to real tickets. |
| `issue_type` | Story/Task/Bug/Sub-task. Used to ensure we only compare same types (Stories with Stories, etc). |
| `summary` | The ticket title. Primary input for semantic similarity search. |
| `description` | Ticket body text. Enriches semantic search with detail about the work. |
| `status` | Current status. Used to filter: only "Done" tickets have valid cycle times. |
| `resolution` | How the ticket was resolved. Used to exclude Cancelled/Duplicate/Rejected tickets. |
| `story_points` | The estimate we're trying to predict. Needed as ground truth for evaluation. |
| `components` | Which part of the system (e.g. "Permit Processing"). Adds context for semantic matching. |
| `labels` | Tags (e.g. "Kogito", "validation"). Adds context for semantic matching. |
| `parent_key` | Epic/parent ticket key. Links tickets to their epic for grouping context. |
| `parent_summary` | Epic/parent title (e.g. "PP Data Model Retrofitting"). Adds semantic context about the work area. |
| `sprint` | Sprint name. Useful metadata but not directly used in estimation. |
| `created` | When ticket was created. Used for time-based train/test split ordering. |
| `changelog` | Status transition history with timestamps. **Critical** — this is the only way to calculate cycle time. |

### Fields We DO NOT Extract (and Why)

| Field | Why We Skip It |
|-------|----------------|
| `assignee` | Who did the work doesn't predict future effort. Different people work at different speeds, but the MVP estimates by ticket similarity, not team member. |
| `reporter` / `creator` | Who reported it doesn't affect effort estimation. |
| `priority` | Priority (High/Medium/Low) indicates urgency, not effort. A P1 bug might take 1 day, a P3 story might take 2 weeks. |
| `comment` | Comments could add context but are noisy (status updates, questions, unrelated discussion). May add in a later version. |
| `attachment` | Binary files — can't embed or search. |
| `fixVersions` | Release version. Not relevant to effort estimation. |
| `duedate` | When it's due doesn't predict how long it takes. |
| `timetracking` / `timespent` / `timeestimate` | Jira time logging is rarely used on this board (all null/zero). |
| `worklog` | Same — no time logging data available. |
| `epic` (full object) | We already extract `parent_key` and `parent_summary` which gives us the epic info we need. |
| `votes` / `watches` | Popularity doesn't predict effort. |
| `environment` | Always null on this board. |
| `issuelinks` | Linked tickets (blocks/is-blocked-by). Could be useful for dependency analysis but not for MVP estimation. |
| `subtasks` | Child ticket list. Not needed — we estimate each ticket independently. |
| `closedSprints` | Historical sprint info. Sprint name already captured. |
| `resolutiondate` | We already calculate this more precisely from the changelog (first Done transition). |
| `updated` | Last modification date — not useful for estimation. |
| 531 custom fields | Mostly internal Jira fields, empty, or irrelevant to effort estimation. The one useful custom field (story points = customfield_10274) is already extracted via auto-discovery. |

### Why Not Extract Everything?

1. **Noise hurts semantic search** — if we dump every field into combined_text, the embedding model gets confused by irrelevant metadata
2. **Storage efficiency** — 578 fields × 1,872 tickets = massive JSON files with 95% null/useless data
3. **Privacy** — assignee names, emails, and internal comments may be sensitive
4. **Simplicity** — fewer fields = easier to debug, understand, and maintain
