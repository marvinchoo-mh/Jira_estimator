# Changelog

## Phase 1 — Jira Extraction
- Added src/config.py with .env loading and validation
- Added src/jira_extract.py with paginated Jira extraction
- Added .env.example with required and optional environment variables
- Added .gitignore to exclude secrets, data files, and local environment
- Added requirements.txt (requests, python-dotenv)
- Implemented story points custom field auto-discovery
- Implemented full changelog extraction for status transition history
- Added data/raw_jira_issues.json output (gitignored)
- Added README.md with setup and usage instructions
- Added docs/FILE_GUIDE.md, docs/CHANGELOG.md, docs/DECISIONS.md
