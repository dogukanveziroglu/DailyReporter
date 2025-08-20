from __future__ import annotations
import streamlit as st
from datetime import timedelta
from app.core.rbac import require_min_role, ROLE_LEAD, is_admin
from app.db.database import SessionLocal
from app.db.repository import list_departments, list_teams, list_users_by_team, list_reports_for_users
from app.services.stats_service import compute_counts
from app.services.export_service import export_reports_dataframe
from app.utils.dates import today_tr
from app.ui.nav import build_sidebar

st.set_page_config(page_title="Raporlama & İstatistik", page_icon="📊", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_LEAD)
def page():
    st.title("📊 Raporlama & İstatistik")
    today = today_tr()
    c1, c2 = st.columns([1,1])
    with c1:
        start_d = st.date_input("Başlangıç", value=today - timedelta(days=7))
    with c2:
        end_d = st.date_input("Bitiş", value=today)

    scope = st.radio("Kapsam", ["Takım", "Departman"], horizontal=True)
    db = SessionLocal()
    try:
        if scope == "Departman":
            deps = list_departments(db)
            dep_id = st.selectbox("Departman", options=[d.id for d in deps], format_func=lambda i: next(d.name for d in deps if d.id==i))
            teams = [t for t in list_teams(db) if t.department_id == dep_id]
        else:
            teams = list_teams(db)
        team_id = st.selectbox("Takım", options=[t.id for t in teams], format_func=lambda i: next(t.name for t in teams if t.id==i))
        members = list_users_by_team(db, team_id=team_id)
        user_ids = [u.id for u in members]
        reports = list_reports_for_users(db, user_ids=user_ids, start=start_d, end=end_d, q=None)
    finally: db.close()

    total_users, total_reports = compute_counts(members, reports)
    st.metric("Üye Sayısı", total_users); st.metric("Rapor Sayısı", total_reports)

    if reports:
        if st.button("CSV İndir"):
            path = export_reports_dataframe(reports)
            st.download_button("CSV İndir (hazır)", data=open(path,"rb").read(), file_name=path.split("/")[-1], mime="text/csv")

if __name__ == "__main__":
    page()
