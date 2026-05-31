import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "VinoJayapalan")
GITHUB_REPO = os.getenv("GITHUB_REPO", "operations-dashboard")
GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "main")
TARGET_REPO_PATH = os.getenv("TARGET_REPO_PATH", "/home/jvino/workspace/operations-dashboard")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "stub")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")