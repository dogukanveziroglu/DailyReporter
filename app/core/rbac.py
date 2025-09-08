from __future__ import annotations
import functools
import streamlit as st

# Kanonik roller
ROLE_ANON = "anon"
ROLE_USER = "user"
ROLE_LEAD = "lead"
ROLE_DEPT_LEAD = "dept_lead"
ROLE_ADMIN = "admin"

# Rol ağırlıkları
role_weight = {
    ROLE_ANON: 0,
    ROLE_USER: 1,
    ROLE_LEAD: 2,
    ROLE_DEPT_LEAD: 3,
    ROLE_ADMIN: 4,
}

# Yaygın yazım/alias'ları kanonik rollere eşle
_ALIAS_MAP = {
    None: ROLE_ANON,
    "": ROLE_ANON,
    # user
    "member": ROLE_USER,
    "employee": ROLE_USER,
    ROLE_USER: ROLE_USER,
    # team lead
    "team_lead": ROLE_LEAD,
    "teamlead": ROLE_LEAD,
    "tl": ROLE_LEAD,
    ROLE_LEAD: ROLE_LEAD,
    # department lead
    "department_lead": ROLE_DEPT_LEAD,
    "deptlead": ROLE_DEPT_LEAD,
    "dep_lead": ROLE_DEPT_LEAD,
    "dl": ROLE_DEPT_LEAD,
    ROLE_DEPT_LEAD: ROLE_DEPT_LEAD,
    # admin
    "administrator": ROLE_ADMIN,
    "superadmin": ROLE_ADMIN,
    "root": ROLE_ADMIN,
    ROLE_ADMIN: ROLE_ADMIN,
}

def normalize_role(r: str | None) -> str:
    if not isinstance(r, str):
        return ROLE_ANON
    return _ALIAS_MAP.get(r.strip().lower(), r.strip().lower())

def current_role() -> str:
    auth = st.session_state.get("auth")
    raw = None
    if auth and auth.get("user_id"):
        raw = auth.get("role", ROLE_USER)
    return normalize_role(raw)

def has_min_role(required: str) -> bool:
    cur = current_role()
    return role_weight.get(cur, 0) >= role_weight.get(required, 0)

def require_min_role(required: str):
    """Sayfa/görünüm guard'ı: oturum yoksa veya rol yetersizse engeller."""
    def deco(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            if not has_min_role(required):
                st.error("Bu sayfayı görüntülemek için giriş yapmanız ve yeterli yetkiye sahip olmanız gerekir.")
                st.stop()
            return func(*a, **kw)
        return wrapper
    return deco

def is_admin() -> bool:
    return current_role() == ROLE_ADMIN

def is_lead() -> bool:
    return current_role() in (ROLE_LEAD, ROLE_DEPT_LEAD, ROLE_ADMIN)

def is_dept_lead() -> bool:
    return current_role() in (ROLE_DEPT_LEAD, ROLE_ADMIN)
