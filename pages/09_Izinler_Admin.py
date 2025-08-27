from __future__ import annotations
import streamlit as st
from datetime import date, timedelta
from typing import List

from app.core.rbac import require_min_role, ROLE_ADMIN
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments, list_users_simple, list_leaves_admin, delete_leave
)
from app.ui.nav import build_sidebar
from app.utils.dates import today_tr

st.set_page_config(page_title="İzinler (Admin)", page_icon="🗓️", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_ADMIN)
def page():
    st.title("🗓️ İzinler (Admin)")

    db = SessionLocal()
    try:
        deps = list_departments(db)
        users = list_users_simple(db)
    finally:
        db.close()

    dep_options = [("ALL", "Tümü")] + [(str(d.id), d.name) for d in deps]
    dep_choice = st.selectbox("Departman", options=[k for k,_ in dep_options],
                              format_func=lambda k: next(lbl for kk,lbl in dep_options if kk==k))
    dep_id = None if dep_choice == "ALL" else int(dep_choice)

    # Kullanıcı filtresi (seçilen departmana göre)
    filtered_users = [u for u in users if (dep_id is None or (u.department and u.department.id == dep_id))]
    user_options = [("ALL", "Tümü")] + [(str(u.id), (u.full_name or u.username)) for u in filtered_users]
    user_choice = st.selectbox("Kullanıcı", options=[k for k,_ in user_options],
                               format_func=lambda k: next(lbl for kk,lbl in user_options if kk==k))
    user_id = None if user_choice == "ALL" else int(user_choice)

    # Tarih aralığı
    today = today_tr()
    default_start = today - timedelta(days=30)
    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("Başlangıç", value=default_start)
    with c2:
        end = st.date_input("Bitiş", value=today)

    # Liste
    db = SessionLocal()
    try:
        leaves = list_leaves_admin(db, start=start, end=end, department_id=dep_id, user_id=user_id)
    finally:
        db.close()

    if not leaves:
        st.info("Kayıt bulunamadı.")
        return

    st.subheader("Kayıtlar")
    for lv in leaves:
        u = lv.user
        owner = (u.full_name or u.username) if u else f"#{lv.user_id}"
        dept_name = (u.department.name if (u and u.department) else "-")
        days = (lv.end_date - lv.start_date).days + 1
        with st.container(border=True):
            st.write(
                f"👤 **{owner}**  ·  🏢 {dept_name}  \n"
                f"📅 **{lv.start_date} → {lv.end_date}**  _(Toplam {days} gün)_  \n"
                f"📝 **Mazeret:** {lv.reason or '-'}"
            )
            col1, col2 = st.columns([1,5])
            with col1:
                if st.button("Sil", key=f"admin_del_{lv.id}"):
                    db = SessionLocal()
                    try:
                        if delete_leave(db, leave_id=lv.id, as_admin=True):
                            st.success("Silindi.")
                        else:
                            st.error("Silinemedi.")
                    finally:
                        db.close()
                    st.rerun()

if __name__ == "__main__":
    page()
