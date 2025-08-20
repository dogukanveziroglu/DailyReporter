from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")
DB_URL = os.getenv("DB_URL", "sqlite:///data/app.sqlite3")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
