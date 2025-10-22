from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
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
ALLOWED_EXT = {"zip", "docx", "pdf"}
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
# Email settings
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")  # Will set this later
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Will set this later
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@business-reporter.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Business Reporter File Exchange")

# Email notifications enabled/disabled
EMAIL_NOTIFICATIONS_ENABLED = os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "1") == "1"
# Timezone settings
import pytz
UK_TIMEZONE = pytz.timezone('Europe/London')  # Handles GMT/BST automatically