"""
Configuration settings for File Exchange App
"""
import os
import secrets
from pathlib import Path

# Application settings
APP_NAME = os.getenv("APP_NAME", "Business Reporter - File Exchange Portal")

# Directory paths
FILES_DIR = Path(os.getenv("FILES_DIR", "files"))
FILES_DIR.mkdir(parents=True, exist_ok=True)
Path("static").mkdir(exist_ok=True)

# Database and logging
AUDIT_LOG = Path(os.getenv("AUDIT_LOG", "audit.log"))
INDEX_FILE = FILES_DIR / ".index.json"
USER_DB_PATH = os.getenv("USER_DB_PATH", "users.db")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
INVITE_CODE = os.getenv("INVITE_CODE", "")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

# File upload settings
ALLOWED_EXT = {"zip"}
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 500 * 1024 * 1024))  # 500MB

# Server settings
PORT = int(os.getenv("PORT", "5000"))

# Stage choices (past tense)
STAGE_CHOICES = [
    "First draft",
    "Rewritten/Updated version",
    "Publisher asked for feedback",
]

# Back-compat mapping for old stage labels
STAGE_ALIASES = {
    "First draft approval": "First draft",
    "First draft approved": "First draft",
    "Rewritten version": "Rewritten/Updated version",
    "Publisher asking for feedback": "Publisher asked for feedback",
    "Feedback required from the publisher": "Publisher asked for feedback",
}

# External links
DASHBOARD_URL = "https://studio.business-reporter.com/abeu5dashboard/index.html"

# Invite code characters for generation
INV_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"