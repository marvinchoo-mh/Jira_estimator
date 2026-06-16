# Changelog

## Phase 5 — Evaluation on Test Tickets
- Added src/evaluate_estimator.py
- Evaluates estimator on 38 test tickets never seen during training
- Saves per-ticket results to data/evaluation_results.csv
- Results: Median SP error = 1.0, Exact SP matches = 5/11 (45%)
- Results: Median CT error = 2.0 days, Range accuracy = 31%
- 22/38 tickets got "Low" confidence (mostly Stories with no training data)

## Phase 4 — Estimation Logic
- Added src/estimate_ticket.py
- Calculates suggested story points via median of similar tickets
- Calculates cycle time range via 25th–75th percentile
- Confidence scoring: High/Medium/Low based on match count, distance, and variance
- Demo output: "Add validation rule" → 5 SP, 6–13 days, High confidence

## Phase 3 — Semantic/Vector Search
- Added src/build_vector_index.py
- Added chromadb and sentence-transformers to requirements.txt
- Using BAAI/bge-small-en-v1.5 embedding model (free, local, no API key)
- Built ChromaDB persistent vector index from train_knowledge_base.csv (151 tickets)
- Provides search_similar_tickets() with issue_type metadata filtering
- Added CHROMA_DB_DIR to config.py
- Added hf_cache/ to .gitignore

## Phase 2 — Data Cleaning and Train/Test Split
- Added src/clean_jira_data.py
- Added src/split_train_test.py
- Implemented cycle-time calculation from "in progress" → Done
- Matches ALL "in progress" status variants: "Dev In Progress", "In Progress", "In Progress / Dev"
- Added combined_text field for future semantic search
- Filters: only Done tickets, excludes bad resolutions, removes outliers >90 working days
- Added time-based 80/20 train/test split (older = train, newer = test)
- Output: cleaned_jira_issues.csv, train_knowledge_base.csv, test_tickets.csv
- Result: 189 cleaned tickets → 151 train / 38 test

## Phase 1 — Jira Extraction
- Added src/config.py with .env loading and validation
- Added src/jira_extract.py with paginated Jira extraction via Agile board API
- Added .gitignore to exclude secrets, data files, and local environment
- Added requirements.txt (requests, python-dotenv)
- Implemented story points custom field auto-discovery (customfield_10274)
- Implemented full changelog extraction for status transition history
- Extracted 1,872 issues from board 520 (TNR PP - Permit Processing)
- Added README.md with setup and usage instructions
- Added docs/FILE_GUIDE.md, docs/CHANGELOG.md, docs/DECISIONS.md
