# Jira Similar Ticket Story Point + Cycle-Time Estimator

## What This Project Does

Given a new Jira ticket from the TNR board, this tool retrieves semantically similar completed historical tickets and estimates:

1. **Suggested story points** (median from similar tickets)
2. **Estimated cycle time** (range in working days from In Progress → Done)

## Current MVP Scope

- Project: `TNR` (board 520) on `https://sgtechstack.atlassian.net`
- Issue types: Story, Task, Bug, Sub-task (no Epics)
- Cycle time: first In Progress → first Done
- Only tickets that reached Done are used (Closed is excluded)

## Setup

### 1. Python Virtual Environment

```bash
cd jira-estimator
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# or: venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env` from `.env.example`

```bash
cp .env.example .env
```

### 4. Add Jira Credentials

Edit `.env` and fill in your real values:

- `JIRA_EMAIL`: Your Atlassian account email
- `JIRA_API_TOKEN`: Generate one at https://id.atlassian.com/manage-profile/security/api-tokens

The other values (`JIRA_SITE_URL`, `JIRA_PROJECT_KEY`, `JIRA_BOARD_ID`) are pre-filled for the TNR board.

### 5. Run Phase 1 — Jira Extraction

```bash
python src/jira_extract.py
```

This extracts all tickets from the TNR project and saves them to `data/raw_jira_issues.json`.

## Output Files

| File | Description |
|------|-------------|
| `data/raw_jira_issues.json` | Raw extracted Jira issues with changelog (Phase 1) |
| `data/cleaned_jira_issues.csv` | Cleaned issues with cycle time (Phase 2, not yet implemented) |
| `data/train_knowledge_base.csv` | Older tickets used as the retrieval index (Phase 2) |
| `data/test_tickets.csv` | Newer tickets used to test estimation accuracy (Phase 2) |
| `data/evaluation_results.csv` | Prediction vs actual results (Phase 5) |

## Git Setup

### Initialize Git

```bash
cd jira-estimator
git init
```

### Push to GitHub

1. Create a new repository on https://github.com (do not initialize with README)
2. Connect and push:

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

### Authentication

Use either:
- **SSH key** (recommended for long-term use): https://docs.github.com/en/authentication/connecting-to-github-with-ssh
- **HTTPS** with personal access token

### Why GitHub API Is Not Needed

Normal version control only requires Git commands (`git add`, `git commit`, `git push`). The GitHub API would only be needed if this app later programmatically creates issues, reads pull requests, or automates repository actions.

## Why `.env` Should Not Be Committed

`.env` contains secrets (Jira API token, OpenAI key). Only `.env.example` is committed — it shows the required variables without real values. The `.gitignore` file prevents accidental commits of `.env` and data files containing company-sensitive Jira content.

## Current Limitations

- Only Phase 1 (extraction) is implemented
- No data cleaning, cycle-time calculation, or estimation yet
- Raw description is stored in Atlassian Document Format (ADF), not plain text
- No semantic search or LLM explanation yet
- Only works with the TNR project / board 520

## Next Steps

- Phase 2: Clean data, calculate cycle time, create train/test split
- Phase 3: Build vector index for semantic search
- Phase 4: Estimation logic (story points + cycle time)
- Phase 5: Evaluate estimator on test tickets
- Phase 6: LLM-generated explanations
