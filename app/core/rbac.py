from __future__ import annotations
import functools
import streamlit as st

ROLE_USER = "user"
ROLE_LEAD = "team_lead"       # Takım lideri
ROLE_DEPT_LEAD = "dept_lead"  # Departman lideri (yeni)
ROLE_ADMIN = "admin"

_ROLE_WEIGHTS = {
    ROLE_USER: 1,
    ROLE_LEAD: 2,
    ROLE_DEPT_LEAD: 2,  # team_lead ile aynı seviye
    ROLE_ADMIN: 3,
}

def role_weight(role: str) -> int:
    return _ROLE_WEIGHTS.get(role, 0)

def is_admin(role: str) -> bool:
    return role == ROLE_ADMIN

def is_lead(role: str) -> bool:
    return role == ROLE_LEAD

def is_dept_lead(role: str) -> bool:
    return role == ROLE_DEPT_LEAD

def require_min_role(min_role: str):
    """Sayfa koruması: min_role ve üzeri roller girebilir."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            auth = st.session_state.get("auth")
            if not auth:
                st.error("Bu sayfa için giriş yapmalısınız.")
                st.stop()
            if role_weight(auth.get("role")) < role_weight(min_role):
                st.error("Bu sayfaya erişim yetkiniz yok.")
                st.stop()
            return func(*a, **kw)
        return wrapper
    return decorator
