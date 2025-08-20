from __future__ import annotations
from typing import Optional
from datetime import date
from app.db.database import SessionLocal
from app.db.repository import upsert_report as _up, list_user_reports as _list, list_reports_for_users as _list_many

def upsert(user_id:int, d:date, content:str, project:Optional[str], tags_json:Optional[str]):
    db=SessionLocal()
    try: return _up(db, user_id=user_id, d=d, content=content, project=project, tags_json=tags_json)
    finally: db.close()

def list_for_user(user_id:int, start:date, end:date, q:Optional[str]):
    db=SessionLocal()
    try: return _list(db, user_id=user_id, start=start, end=end, q=q)
    finally: db.close()

def list_for_many(user_ids, start, end, q):
    db=SessionLocal()
    try: return _list_many(db, user_ids=list(user_ids), start=start, end=end, q=q)
    finally: db.close()
