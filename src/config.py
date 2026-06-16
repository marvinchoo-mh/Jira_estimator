"""
config.py

Loads environment variables from .env and validates that required values
are present. Provides configuration constants used by other modules.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Required environment variables for Phase 1 ---

REQUIRED_VARS = [
    "JIRA_SITE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_KEY",
    "JIRA_BOARD_ID",
]


def validate_env():
    """Check that all required environment variables are set."""
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        for var in missing:
            print(
                f"Missing required environment variable: {var}.\n"
                f"Please add it to your .env file. See .env.example for the expected format.\n"
            )
        sys.exit(1)


validate_env()

# --- Jira configuration ---

JIRA_SITE_URL = os.getenv("JIRA_SITE_URL").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")
JIRA_BOARD_ID = os.getenv("JIRA_BOARD_ID")

# --- File paths ---

DATA_DIR = PROJECT_ROOT / "data"
RAW_JIRA_FILE = DATA_DIR / "raw_jira_issues.json"

# --- Optional environment variables (not required for Phase 1) ---

CONFLUENCE_SITE_URL = os.getenv("CONFLUENCE_SITE_URL")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
