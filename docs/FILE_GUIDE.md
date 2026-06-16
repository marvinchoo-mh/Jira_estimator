# File Guide

## src/config.py
Stores configuration values such as Jira site URL, board ID, project key, file paths, and environment variable names. It also validates that required .env values are present.

## src/jira_extract.py
Connects to Jira and extracts raw ticket data from board 520 (TNR PP). Auto-discovers the story points custom field, paginates through all issues, includes changelog for status transitions, and saves the raw output to data/raw_jira_issues.json.

## src/clean_jira_data.py
Cleans the raw Jira data, calculates cycle time (first "in progress" → first "Done"), creates combined_text for semantic search, filters out incomplete/invalid tickets, and saves cleaned_jira_issues.csv.

## src/split_train_test.py
Splits cleaned tickets into older training/knowledge-base tickets (80%) and newer test tickets (20%) using a time-based split on first_done_at.

## .gitignore
Prevents secrets, local environment files, raw Jira data, and generated vector databases from being committed.

## requirements.txt
Lists Python package dependencies needed to run the project.

## README.md
Project overview, setup instructions, how to run each phase, and current limitations.

## docs/FILE_GUIDE.md
This file. Explains what each file does in plain English.

## docs/CHANGELOG.md
Tracks implementation progress by phase.

## docs/DECISIONS.md
Explains why important design choices were made.
