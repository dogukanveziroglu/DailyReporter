from __future__ import annotations
import os
from app.db.database import Base, engine
from app.db.repository import get_user_by_username, create_user
from app.core.config import ADMIN_USERNAME, ADMIN_PASSWORD

def create_tables(): Base.metadata.create_all(bind=engine)
def ensure_dirs():
    os.makedirs("data", exist_ok=True); os.makedirs("data/uploads", exist_ok=True)

def ensure_admin():
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        if not get_user_by_username(db, ADMIN_USERNAME):
            create_user(db, username=ADMIN_USERNAME, password=ADMIN_PASSWORD, full_name="Admin", role="admin",
                        department_id=None, team_id=None)
    finally: db.close()
