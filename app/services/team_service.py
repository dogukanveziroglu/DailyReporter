from __future__ import annotations
from app.db.database import SessionLocal
from app.db.repository import list_teams_for_lead as _teams, list_users_by_team as _members

def my_teams(lead_user_id:int):
    db=SessionLocal()
    try: return _teams(db, lead_user_id=lead_user_id)
    finally: db.close()

def members(team_id:int):
    db=SessionLocal()
    try: return _members(db, team_id=team_id)
    finally: db.close()
