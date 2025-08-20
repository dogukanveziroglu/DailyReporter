from __future__ import annotations
from typing import Optional
from app.db.database import SessionLocal
from app.db.repository import create_user as _create, update_user_role_team_dept as _update
from app.utils.text import make_username

def create_user(full_name:str, password:str, role:str="user", department_id:Optional[int]=None, team_id:Optional[int]=None):
    username = make_username(full_name)
    db=SessionLocal()
    try: return _create(db, username=username, password=password, full_name=full_name, role=role, department_id=department_id, team_id=team_id)
    finally: db.close()

def update_user(user_id:int, role:str, department_id:Optional[int], team_id:Optional[int]):
    db=SessionLocal()
    try: _update(db, user_id=user_id, role=role, department_id=department_id, team_id=team_id)
    finally: db.close()
