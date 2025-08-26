from __future__ import annotations
from typing import Optional, List, Dict, Tuple
from datetime import date, datetime
import json

from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.db.models import User, Report, Department, Team, Comment, Todo
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
        r.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(r)
        return r
    r = Report(
        user_id=user_id, date=d, content=content, project=project, tags_json=tags_json
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
    """İdeal: aynı gün için YENİ satır.
    Eğer DB'de (user_id, date) UNIQUE varsa, geçici olarak mevcut satırı günceller."""
    tags = {"edited": True, "edited_at": edited_at_iso}
    r = Report(
        user_id=user_id,
        date=d,
        content=content,
        project=project,
        tags_json=json.dumps(tags, ensure_ascii=False),
    )
    db.add(r)
    try:
        db.commit()
        db.refresh(r)
        return r
    except IntegrityError as e:
        db.rollback()
        if "reports.user_id, reports.date" in str(e):
            existing = get_report(db, user_id=user_id, d=d)
            if existing:
                try:
                    t = json.loads(existing.tags_json or "{}")
                    if not isinstance(t, dict):
                        t = {}
                except Exception:
                    t = {}
                t["edited"] = True
                t["edited_at"] = edited_at_iso
                existing.content = content
                existing.project = project
                existing.tags_json = json.dumps(t, ensure_ascii=False)
                existing.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                return existing
        raise

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
# COMMENTS (yorum & yanıt)
# -------------------------
def add_comment(
    db: Session,
    *,
    report_id: int,
    author_user_id: int,
    content: str,
    parent_comment_id: Optional[int] = None,
) -> Comment:
    c = Comment(
        report_id=report_id,
        author_user_id=author_user_id,
        content=content.strip(),
        parent_comment_id=parent_comment_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def list_comments_tree_by_report_ids(
    db: Session, *, report_ids: List[int]
) -> Dict[int, List[Tuple[Comment, int]]]:
    """Her rapor için (yorum, depth) listesi döner (depth = iç içe seviye)."""
    if not report_ids:
        return {}
    stmt = (
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.report_id.in_(report_ids))
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )
    all_comments = list(db.execute(stmt).scalars().all())

    # report_id -> [comments]
    per_report: Dict[int, List[Comment]] = {}
    for c in all_comments:
        per_report.setdefault(c.report_id, []).append(c)

    # Her rapor için ağaç oluştur
    out: Dict[int, List[Tuple[Comment, int]]] = {}
    for rid, arr in per_report.items():
        children: Dict[Optional[int], List[Comment]] = {}
        for c in arr:
            children.setdefault(c.parent_comment_id, []).append(c)

        # her seviyede kronolojik sırayı koru
        for k in children:
            children[k].sort(key=lambda x: (x.created_at, x.id))

        ordered: List[Tuple[Comment, int]] = []

        def walk(parent_id: Optional[int], depth: int):
            for c in children.get(parent_id, []):
                ordered.append((c, depth))
                walk(c.id, depth + 1)

        walk(None, 0)
        out[rid] = ordered

    return out

# -------------------------
# TODOS
# -------------------------
def create_todo(
    db: Session,
    *,
    user_id: int,
    title: str,
    description: Optional[str] = None,
    due_date: Optional[date] = None,
    priority: int = 2,
) -> Todo:
    t = Todo(
        user_id=user_id,
        title=title.strip(),
        description=(description or None),
        due_date=due_date,
        priority=priority,
        is_done=False,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def list_todos_for_user(
    db: Session,
    *,
    user_id: int,
    show_done: Optional[bool] = None,
    search: Optional[str] = None,
    only_overdue: bool = False,
) -> List[Todo]:
    stmt = select(Todo).where(Todo.user_id == user_id)
    if show_done is not None:
        stmt = stmt.where(Todo.is_done.is_(show_done))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Todo.title.ilike(like), Todo.description.ilike(like)))
    if only_overdue:
        stmt = stmt.where(and_(Todo.due_date.is_not(None), Todo.due_date < func.date("now")))
    stmt = stmt.order_by(
        Todo.is_done.asc(), Todo.due_date.is_(None).asc(), Todo.due_date.asc(),
        Todo.priority.desc(), Todo.created_at.desc()
    )
    return list(db.execute(stmt).scalars().all())

def update_todo(
    db: Session,
    *,
    todo_id: int,
    user_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[date] = None,
    priority: Optional[int] = None,
) -> Optional[Todo]:
    t = db.get(Todo, todo_id)
    if not t or t.user_id != user_id:
        return None
    if title is not None:
        t.title = title.strip() or t.title
    if description is not None:
        t.description = (description or None)
    if due_date is not None or due_date is None:
        t.due_date = due_date
    if priority is not None:
        t.priority = priority
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t

def toggle_todo_done(db: Session, *, todo_id: int, user_id: int, done: bool) -> Optional[Todo]:
    t = db.get(Todo, todo_id)
    if not t or t.user_id != user_id:
        return None
    t.is_done = bool(done)
    t.completed_at = datetime.utcnow() if done else None
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t

def delete_todo(db: Session, *, todo_id: int, user_id: int) -> bool:
    t = db.get(Todo, todo_id)
    if not t or t.user_id != user_id:
        return False
    db.delete(t)
    db.commit()
    return True
