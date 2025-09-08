from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional, List, Dict, Tuple

from sqlalchemy import select, or_, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    User, Department, Team,
    UserDepartment,
    Report, Comment,
    Todo, Leave,
)
from app.core.security import hash_password, verify_password
from app.core.rbac import ROLE_LEAD


# --------------------------------
# USERS
# --------------------------------

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    stmt = (
        select(User)
        .options(
            selectinload(User.departments),
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
    department_ids: Optional[List[int]] = None,
    team_id: Optional[int] = None,
) -> User:
    u = User(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
        team_id=team_id,
    )
    db.add(u)
    db.flush()  # id üret
    # çoklu departman
    if department_ids:
        for did in set(department_ids):
            db.add(UserDepartment(user_id=u.id, department_id=did))
    db.commit()
    db.refresh(u)
    return u


def reset_password_for_user(db: Session, *, user_id: int, new_password: str) -> None:
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


def update_user_role_team(
    db: Session,
    *,
    user_id: int,
    role: str,
    team_id: Optional[int],
) -> None:
    u = db.get(User, user_id)
    if not u:
        raise ValueError("User not found")
    u.role = role
    u.team_id = team_id
    db.commit()


def set_user_departments(db: Session, *, user_id: int, department_ids: List[int]) -> None:
    """
    Kullanıcının departmanlarını tamamen senkronize eder (ekle/sil).
    """
    department_ids = sorted(set(int(x) for x in department_ids))
    # mevcut
    rows = db.execute(
        select(UserDepartment).where(UserDepartment.user_id == user_id)
    ).scalars().all()
    existing = {r.department_id for r in rows}

    # eklenecek
    for did in department_ids:
        if did not in existing:
            db.add(UserDepartment(user_id=user_id, department_id=did))

    # silinecek
    for did in existing:
        if did not in department_ids:
            db.query(UserDepartment).filter(
                UserDepartment.user_id == user_id,
                UserDepartment.department_id == did
            ).delete(synchronize_session=False)

    db.commit()


def get_user_department_ids(db: Session, *, user_id: int) -> List[int]:
    return list(db.execute(
        select(UserDepartment.department_id).where(UserDepartment.user_id == user_id)
    ).scalars().all())


def list_departments_for_user(db: Session, *, user_id: int) -> List[Department]:
    stmt = (
        select(Department)
        .join(UserDepartment, UserDepartment.department_id == Department.id)
        .where(UserDepartment.user_id == user_id)
        .order_by(Department.name)
    )
    return list(db.execute(stmt).scalars().all())


def list_user_ids_in_department(db: Session, *, department_id: int) -> List[int]:
    return list(db.execute(
        select(UserDepartment.user_id).where(UserDepartment.department_id == department_id)
    ).scalars().all())


def delete_user(db: Session, *, user_id: int) -> None:
    # takım lideri ise temizle
    for t in db.execute(select(Team).where(Team.lead_user_id == user_id)).scalars():
        t.lead_user_id = None
    u = db.get(User, user_id)
    if not u:
        raise ValueError("User not found")
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
        .options(selectinload(User.departments), selectinload(User.team))
        .order_by(User.id)
    )
    return list(db.execute(stmt).scalars().all())


def list_users_by_team(db: Session, *, team_id: int) -> List[User]:
    stmt = (
        select(User)
        .options(selectinload(User.departments), selectinload(User.team))
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


# --------------------------------
# DEPARTMENTS & TEAMS
# --------------------------------

def list_departments(db: Session) -> List[Department]:
    return list(db.execute(select(Department).order_by(Department.name)).scalars().all())


def create_department(db: Session, *, name: str) -> Department:
    d = Department(name=name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def list_teams(db: Session) -> List[Team]:
    stmt = select(Team).options(selectinload(Team.department)).order_by(Team.name)
    return list(db.execute(stmt).scalars().all())


def create_team(
    db: Session, *, name: str, department_id: Optional[int], lead_user_id: Optional[int] = None
) -> Team:
    t = Team(name=name, department_id=department_id, lead_user_id=lead_user_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# --------------------------------
# REPORTS
# --------------------------------

def get_report_by_user_dept_date(db: Session, *, user_id: int, department_id: int, d: date) -> Optional[Report]:
    stmt = select(Report).where(
        Report.user_id == user_id,
        Report.department_id == department_id,
        Report.date == d,
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert_report(
    db: Session,
    *,
    user_id: int,
    department_id: int,
    d: date,
    content: str,
    project: Optional[str],
    tags_json: Optional[str],
) -> Report:
    """
    Aynı gün/aynı departman için tek rapor kuralı: (user_id, department_id, date).
    """
    r = get_report_by_user_dept_date(db, user_id=user_id, department_id=department_id, d=d)
    if r:
        r.content = content
        r.project = project
        r.tags_json = tags_json
        r.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(r)
        return r

    r = Report(
        user_id=user_id,
        department_id=department_id,
        date=d,
        content=content,
        project=project,
        tags_json=tags_json,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def create_report_revision(
    db: Session,
    *,
    user_id: int,
    department_id: int,
    d: date,
    content: str,
    project: Optional[str],
    edited_at_iso: str,
) -> Report:
    """
    Yeni kayıt dene; UNIQUE ihlalinde mevcut kaydı güncelle.
    """
    tags = {"edited": True, "edited_at": edited_at_iso}
    r = Report(
        user_id=user_id,
        department_id=department_id,
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
        existing = get_report_by_user_dept_date(db, user_id=user_id, department_id=department_id, d=d)
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
    db: Session, *, user_id: int, start: date, end: date, q: Optional[str] = None, department_id: Optional[int] = None
) -> List[Report]:
    stmt = (
        select(Report)
        .where(Report.user_id == user_id, Report.date >= start, Report.date <= end)
        .order_by(Report.date.desc(), Report.id.desc())
    )
    if department_id:
        stmt = stmt.where(Report.department_id == department_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Report.content.ilike(like), Report.project.ilike(like)))
    return list(db.execute(stmt).scalars().all())


def list_reports_for_department(
    db: Session, *, department_id: int, d: date
) -> List[Report]:
    stmt = (
        select(Report)
        .where(Report.department_id == department_id, Report.date == d)
        .order_by(Report.created_at.asc(), Report.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_reports_for_users(
    db: Session, *, user_ids: List[int], start: date, end: date, q: Optional[str]
) -> List[Report]:
    """
    (Eski kullanım için) kullanıcı listesine göre raporlar. Departman filtrelemek istiyorsanız
    list_reports_for_department kullanın veya WHERE Report.department_id ... ekleyin.
    """
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


def missing_reports_for_department_and_date(
    db: Session, *, department_id: int, d: date
) -> List[User]:
    """
    O departmana atanmış kullanıcılar içinde, seçilen gün rapor yazmamış olanları döndür.
    """
    user_ids = set(list_user_ids_in_department(db, department_id=department_id))
    if not user_ids:
        return []
    reported = set(
        db.execute(
            select(Report.user_id).where(
                Report.department_id == department_id, Report.date == d, Report.user_id.in_(user_ids)
            )
        ).scalars().all()
    )
    missing_ids = [uid for uid in user_ids if uid not in reported]
    # kullanıcı objelerini sırayla döndür
    if not missing_ids:
        return []
    stmt = select(User).where(User.id.in_(missing_ids)).order_by(User.full_name, User.username)
    return list(db.execute(stmt).scalars().all())


# --------------------------------
# COMMENTS (threaded)
# --------------------------------

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
        content=(content or "").strip(),
        parent_comment_id=parent_comment_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_comments_tree_by_report_ids(
    db: Session, *, report_ids: List[int]
) -> Dict[int, List[Tuple[Comment, int]]]:
    if not report_ids:
        return {}
    stmt = (
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.report_id.in_(report_ids))
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )
    all_comments = list(db.execute(stmt).scalars().all())

    per_report: Dict[int, List[Comment]] = {}
    for c in all_comments:
        per_report.setdefault(c.report_id, []).append(c)

    out: Dict[int, List[Tuple[Comment, int]]] = {}

    for rid, arr in per_report.items():
        children: Dict[Optional[int], List[Comment]] = {}
        for c in arr:
            children.setdefault(c.parent_comment_id, []).append(c)
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


# --------------------------------
# TODOS
# --------------------------------

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
        title=(title or "").strip(),
        description=(description or None),
        due_date=due_date,
        priority=priority,
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
        Todo.is_done.asc(),
        Todo.due_date.is_(None).asc(),
        Todo.due_date.asc(),
        Todo.priority.desc(),
        Todo.created_at.desc(),
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
    t.due_date = due_date  # None atanabilsin
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


# --------------------------------
# LEAVES (İzin)
# --------------------------------

def create_leave(
    db: Session,
    *,
    user_id: int,
    start_date: date,
    end_date: date,
    reason: Optional[str],
) -> Leave:
    if start_date > end_date:
        raise ValueError("Başlangıç tarihi bitişten büyük olamaz")
    lv = Leave(user_id=user_id, start_date=start_date, end_date=end_date, reason=(reason or None))
    db.add(lv)
    db.commit()
    db.refresh(lv)
    return lv


def list_leaves_for_user(
    db: Session,
    *,
    user_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[Leave]:
    stmt = select(Leave).where(Leave.user_id == user_id)
    if start:
        stmt = stmt.where(Leave.end_date >= start)
    if end:
        stmt = stmt.where(Leave.start_date <= end)
    stmt = stmt.order_by(Leave.start_date.desc(), Leave.id.desc())
    return list(db.execute(stmt).scalars().all())


def list_leaves_admin(
    db: Session,
    *,
    start: Optional[date] = None,
    end: Optional[date] = None,
    department_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> List[Leave]:
    from app.db.models import User  # circular import guard
    stmt = select(Leave).options(selectinload(Leave.user).selectinload(User.departments))
    if start:
        stmt = stmt.where(Leave.end_date >= start)
    if end:
        stmt = stmt.where(Leave.start_date <= end)
    if user_id:
        stmt = stmt.where(Leave.user_id == user_id)
    if department_id:
        stmt = stmt.join(UserDepartment, UserDepartment.user_id == Leave.user_id).where(
            UserDepartment.department_id == department_id
        )
    stmt = stmt.order_by(Leave.start_date.desc(), Leave.id.desc())
    return list(db.execute(stmt).scalars().all())


def delete_leave(db: Session, *, leave_id: int, user_id: Optional[int] = None, as_admin: bool = False) -> bool:
    lv = db.get(Leave, leave_id)
    if not lv:
        return False
    if not as_admin and (user_id is None or lv.user_id != user_id):
        return False
    db.delete(lv)
    db.commit()
    return True
