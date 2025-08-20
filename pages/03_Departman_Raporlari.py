from __future__ import annotations
import streamlit as st
from datetime import date
from typing import List
from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments, list_users_simple, list_reports_for_users, missing_reports_for_date,
    list_comments_by_report_ids
)
from app.utils.dates import today_tr, fmt_hm_tr, parse_iso_dt
from app.ui.nav import build_sidebar

st.set_page_config(page_title="Departman Raporları", page_icon="🏢", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_USER)
def page():
    st.title("🏢 Departman Raporları")

    db = SessionLocal()
    try:
        deps = list_departments(db)
        users_all = list_users_simple(db)
    finally:
        db.close()

    if not deps:
        st.info("Sistemde departman bulunmuyor.")
        return

    dep_id = st.selectbox(
        "Departman",
        options=[d.id for d in deps],
        format_func=lambda i: next(d.name for d in deps if d.id == i),
    )

    d: date = st.date_input("Tarih", value=today_tr())

    user_ids: List[int] = [u.id for u in users_all if (u.department and u.department.id == dep_id)]
    if not user_ids:
        st.info("Seçilen departmanda kullanıcı bulunmuyor.")
        return

    name_map = {u.id: (u.full_name or u.username) for u in users_all}

    st.subheader("Raporlar")
    db = SessionLocal()
    try:
        reports = list_reports_for_users(db, user_ids=user_ids, start=d, end=d, q=None)
        comments_map = list_comments_by_report_ids(db, report_ids=[r.id for r in reports])
    finally:
        db.close()

    if not reports:
        st.info("Seçilen günde rapor bulunmuyor.")
    else:
        for r in reports:
            owner = name_map.get(r.user_id, f"#{r.user_id}")
            with st.expander(f"👤 {owner} · 📅 {r.date} · 🏷️ {r.project or '-'}", expanded=False):
                st.markdown(r.content)

                # Yorumlar (read-only)
                cmts = comments_map.get(r.id, [])
                if cmts:
                    st.markdown("**Yorumlar**")
                    for c in cmts:
                        who = name_map.get(c.author_user_id, f"#{c.author_user_id}")
                        st.write(f"• _{who}_ — {fmt_hm_tr(parse_iso_dt(c.created_at.isoformat()))}")
                        st.markdown(f"> {c.content}")
                else:
                    st.caption("Henüz yorum yok.")

    st.divider()
    st.subheader("Eksik Raporlar (Seçilen Gün)")
    db = SessionLocal()
    try:
        missing = missing_reports_for_date(db, user_ids=user_ids, d=d)
    finally:
        db.close()

    if not missing:
        st.success("Seçilen günde eksik rapor yok.")
    else:
        for u in missing:
            st.warning(f"• {name_map.get(u.id, u.username)}")

if __name__ == "__main__":
    page()
