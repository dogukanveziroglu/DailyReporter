from __future__ import annotations
import streamlit as st
from app.core.rbac import (
    ROLE_ANON, ROLE_USER, ROLE_LEAD, ROLE_DEPT_LEAD, ROLE_ADMIN,
    role_weight, current_role, normalize_role
)

def _auth_info():
    auth = st.session_state.get("auth") or {}
    username = auth.get("username")
    # Kanonik rol ismini gösterelim
    role = current_role()
    full_name = auth.get("full_name") or username or "-"
    return full_name, role

def _safe_page_link(path: str, label: str, icon: str = ""):
    try:
        st.sidebar.page_link(path, label=f"{icon} {label}".strip())
    except Exception:
        st.sidebar.write(f"{icon} {label}")

def build_sidebar():
    st.sidebar.markdown("### 📝 Günlük Raporlama")

    # Giriş yoksa sadece "Giriş"
    if "auth" not in st.session_state or not st.session_state["auth"].get("user_id"):
        st.sidebar.info("Lütfen giriş yapın.")
        _safe_page_link("streamlit_app.py", "Giriş", "🔐")
        return

    full_name, role = _auth_info()
    st.sidebar.caption(f"Giriş yapan: **{full_name}**  \nRol: **{role}**")

    # Herkese açık (giriş yapmış kullanıcı) sayfalar
    _safe_page_link("streamlit_app.py", "Ana Sayfa", "🏠")
    _safe_page_link("pages/01_Rapor_Yaz.py", "Rapor Yaz", "📝")
    _safe_page_link("pages/02_Gecmisim.py", "Geçmişim", "📜")
    _safe_page_link("pages/03_Departman_Raporlari.py", "Departman Raporları", "🏢")

    # Admin sayfaları
    if role == ROLE_ADMIN:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Admin Paneli**")
        _safe_page_link("pages/05_Raporlama_Istatistik.py", "Raporlama & İstatistik", "📊")
        _safe_page_link("pages/04_Yonetim.py", "Yönetim", "🛠️")

    st.sidebar.markdown("---")
    _safe_page_link("pages/99_Cikis.py", "Çıkış", "🚪")

