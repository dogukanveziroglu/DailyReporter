from __future__ import annotations
import json
from app.db.database import SessionLocal
from app.db.models import AuditLog

def audit(actor_user_id:int, action:str, entity:str, entity_id:int, diff:dict|None=None):
    db=SessionLocal()
    try:
        db.add(AuditLog(actor_user_id=actor_user_id, action=action, entity=entity, entity_id=entity_id,
                        diff_json=(json.dumps(diff, ensure_ascii=False) if diff else None)))
        db.commit()
    finally: db.close()
