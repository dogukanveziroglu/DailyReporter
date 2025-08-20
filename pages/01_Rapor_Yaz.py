from __future__ import annotations
import streamlit as st
from datetime import date
from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import get_report, upsert_report
from app.utils.dates import today_tr, is_future
from app.ui.nav import build_sidebar

st.set_page_config(page_title="...", page_icon="...", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_USER)
def page():
    st.title("📝 Rapor Yaz")
    auth = st.session_state["auth"]
    selected_date: date = st.date_input("Tarih", value=today_tr())
    if is_future(selected_date):
        st.warning("Gelecek tarihe rapor girilemez."); st.stop()

    db = SessionLocal()
    try:
        existing = get_report(db, user_id=auth["user_id"], d=selected_date)
    finally: db.close()

    with st.form("report_form", clear_on_submit=False):
        project = st.text_input("Proje (opsiyonel)", value=(existing.project if existing else "") or "")
        content = st.text_area("Bugün neler yaptın?", value=(existing.content if existing else ""), height=240)
        ok = st.form_submit_button("Kaydet")
    if ok:
        if not content.strip():
            st.error("İçerik boş olamaz."); st.stop()
        db = SessionLocal()
        try:
            upsert_report(db, user_id=auth["user_id"], d=selected_date,
                          content=content.strip(), project=(project.strip() or None), tags_json=None)
        finally: db.close()
        st.success("Kaydedildi ✔")

if __name__ == "__main__":
    page()
