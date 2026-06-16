# File Guide

## src/config.py
Stores configuration values such as Jira site URL, board ID, project key, file paths, and environment variable names. It also validates that required .env values are present.

## src/jira_extract.py
Connects to Jira and extracts raw ticket data from project TNR. Auto-discovers the story points custom field, paginates through all issues, includes changelog for status transitions, and saves the raw output to data/raw_jira_issues.json.

## .env.example
Shows the environment variables needed to run the project without exposing real secrets.

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
