from __future__ import annotations
from typing import Optional, List, Dict
from datetime import date, datetime
import json

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.db.models import User, Report, Department, Team, Comment
from app.core.security import hash_password, verify_password
from app.core.rbac import ROLE_LEAD

# -------------------------
# USERS
# -------------------------
def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    stmt = (
        select(User)
        .options(
            selectinload(User.department),
            selectinload(User.team),
        )
        .where(User.username == username)
    )
    return db.execute(stmt).scalar_one_or_none()

def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    full_name: Optional[str],
    role: str = "user",
    department_id: Optional[int] = None,
    team_id: Optional[int] = None,
) -> User:
    u = User(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
        department_id=department_id,
        team_id=team_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def reset_password_for_user(db: Session, *, user_id: int, new_password: str):
    u = db.get(User, user_id)
    if not u:
        raise ValueError("User not found")
    u.password_hash = hash_password(new_password)
    db.commit()

def change_password(db: Session, *, user_id: int, old_password: str, new_password: str) -> bool:
    u = db.get(User, user_id)
    if not u:
        return False
    if not verify_password(old_password, u.password_hash):
        return False
    u.password_hash = hash_password(new_password)
    db.commit()
    return True

def update_user_role_team_dept(
    db: Session, *, user_id: int, role: str, department_id: Optional[int], team_id: Optional[int]
):
    u = db.get(User, user_id)
    if not u:
        raise ValueError("User not found")
    u.role = role
    u.department_id = department_id
    u.team_id = team_id
    db.commit()

def delete_user(db: Session, *, user_id: int):
    u = db.get(User, user_id)
    if not u:
        raise ValueError("User not found")
    teams = list(db.execute(select(Team).where(Team.lead_user_id == user_id)).scalars())
    for t in teams:
        t.lead_user_id = None
    db.delete(u)
    db.commit()

def authenticate_user(db: Session, *, username: str, password: str) -> Optional[User]:
    u = get_user_by_username(db, username)
    if not u:
        return None
    return u if verify_password(password, u.password_hash) else None

def list_users_simple(db: Session) -> List[User]:
    stmt = (
        select(User)
        .options(
            selectinload(User.department),
            selectinload(User.team),
        )
        .order_by(User.id)
    )
    return list(db.execute(stmt).scalars().all())

def list_users_by_team(db: Session, *, team_id: int) -> List[User]:
    stmt = (
        select(User)
        .options(
            selectinload(User.department),
            selectinload(User.team),
        )
        .where(User.team_id == team_id)
        .order_by(User.full_name, User.username)
    )
    return list(db.execute(stmt).scalars().all())

def list_team_leads_by_team(db: Session, *, team_id: int) -> List[User]:
    stmt = (
        select(User)
        .where(User.team_id == team_id, User.role == ROLE_LEAD)
        .order_by(User.full_name, User.username)
    )
    return list(db.execute(stmt).scalars().all())

# -------------------------
# DEPARTMENTS & TEAMS
# -------------------------
def list_departments(db: Session) -> List[Department]:
    stmt = select(Department).order_by(Department.name)
    return list(db.execute(stmt).scalars().all())

def create_department(db: Session, *, name: str) -> Department:
    d = Department(name=name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d

def list_teams(db: Session) -> List[Team]:
    stmt = (
        select(Team)
        .options(selectinload(Team.department))
        .order_by(Team.name)
    )
    return list(db.execute(stmt).scalars().all())

def list_teams_for_lead(
    db: Session, *, lead_user_id: Optional[int], include_all: bool = False
) -> List[Team]:
    if include_all:
        return list_teams(db)
    if not lead_user_id:
        return []
    u = db.get(User, lead_user_id)
    if not u or not u.team_id:
        return []
    stmt = select(Team).options(selectinload(Team.department)).where(Team.id == u.team_id)
    return list(db.execute(stmt).scalars().all())

def create_team(
    db: Session, *, name: str, department_id: Optional[int], lead_user_id: Optional[int] = None
) -> Team:
    t = Team(name=name, department_id=department_id, lead_user_id=lead_user_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

# -------------------------
# REPORTS
# -------------------------
def get_report(db: Session, *, user_id: int, d: date) -> Optional[Report]:
    stmt = select(Report).where(Report.user_id == user_id, Report.date == d)
    return db.execute(stmt).scalar_one_or_none()

def upsert_report(
    db: Session,
    *,
    user_id: int,
    d: date,
    content: str,
    project: Optional[str],
    tags_json: Optional[str],
) -> Report:
    r = get_report(db, user_id=user_id, d=d)
    if r:
        r.content = content
        r.project = project
        r.tags_json = tags_json
        r.updated_at = datetime.utcnow()  # ← kritik
        db.commit()
        db.refresh(r)
        return r
    r = Report(
        user_id=user_id, date=d, content=content, project=project, tags_json=tags_json
        # created_at ve updated_at otomatik dolacak
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def create_report_revision(
    db: Session,
    *,
    user_id: int,
    d: date,
    content: str,
    project: Optional[str],
    edited_at_iso: str,
) -> Report:
    tags = {"edited": True, "edited_at": edited_at_iso}
    r = Report(
        user_id=user_id,
        date=d,
        content=content,
        project=project,
        tags_json=json.dumps(tags, ensure_ascii=False),
        # created_at/updated_at otomatik
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def list_user_reports(
    db: Session, *, user_id: int, start: date, end: date, q: Optional[str]
) -> List[Report]:
    stmt = (
        select(Report)
        .where(Report.user_id == user_id, Report.date >= start, Report.date <= end)
        .order_by(Report.date.desc(), Report.id.desc())
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Report.content.ilike(like), Report.project.ilike(like)))
    return list(db.execute(stmt).scalars().all())

def list_reports_for_users(
    db: Session, *, user_ids: List[int], start: date, end: date, q: Optional[str]
) -> List[Report]:
    if not user_ids:
        return []
    stmt = (
        select(Report)
        .where(Report.user_id.in_(user_ids), Report.date >= start, Report.date <= end)
        .order_by(Report.date.desc(), Report.id.desc())
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Report.content.ilike(like), Report.project.ilike(like)))
    return list(db.execute(stmt).scalars().all())

def missing_reports_for_date(db: Session, *, user_ids: List[int], d: date) -> List[User]:
    if not user_ids:
        return []
    reported_user_ids = set(
        db.execute(select(Report.user_id).where(Report.user_id.in_(user_ids), Report.date == d))
        .scalars()
        .all()
    )
    return [db.get(User, uid) for uid in user_ids if uid not in reported_user_ids]

# -------------------------
# COMMENTS
# -------------------------
def add_comment(db: Session, *, report_id: int, author_user_id: int, content: str) -> Comment:
    c = Comment(report_id=report_id, author_user_id=author_user_id, content=content.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def list_comments_for_report(db: Session, *, report_id: int) -> List[Comment]:
    stmt = (
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.report_id == report_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )
    return list(db.execute(stmt).scalars().all())

def list_comments_by_report_ids(db: Session, *, report_ids: List[int]) -> Dict[int, List[Comment]]:
    if not report_ids:
        return {}
    stmt = (
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.report_id.in_(report_ids))
        .order_by(Comment.report_id.asc(), Comment.created_at.asc(), Comment.id.asc())
    )
    out: Dict[int, List[Comment]] = {}
    for c in db.execute(stmt).scalars().all():
        out.setdefault(c.report_id, []).append(c)
    return out
