from __future__ import annotations
import streamlit as st
from datetime import date
from typing import List

from app.core.rbac import require_min_role, ROLE_USER, ROLE_ADMIN
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments, list_users_simple,
    list_reports_for_users, missing_reports_for_date,
    list_comments_tree_by_report_ids, add_comment,
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

    # Seçilen departmandaki kullanıcılar
    user_ids: List[int] = [u.id for u in users_all if (u.department and u.department.id == dep_id)]
    if not user_ids:
        st.info("Seçilen departmanda kullanıcı bulunmuyor.")
        return

    # İsim haritası
    name_map = {u.id: (u.full_name or u.username) for u in users_all}

    auth = st.session_state.get("auth") or {}
    current_uid = auth.get("user_id")
    current_role = auth.get("role", "user")

    # ---------- Raporlar
    st.subheader("Raporlar")
    db = SessionLocal()
    try:
        reports = list_reports_for_users(db, user_ids=user_ids, start=d, end=d, q=None)
        tree_map = list_comments_tree_by_report_ids(db, report_ids=[r.id for r in reports])
    finally:
        db.close()

    if not reports:
        st.info("Seçilen günde rapor bulunmuyor.")
    else:
        for r in reports:
            owner = name_map.get(r.user_id, f"#{r.user_id}")
            with st.expander(f"👤 {owner} · 📅 {r.date} · 🏷️ {r.project or '-'}", expanded=False):
                st.markdown(r.content)

                # Yorumlar (herkes okur)
                cmts = tree_map.get(r.id, [])
                if cmts:
                    st.markdown("**Yorumlar**")
                    for c, depth in cmts:
                        who = name_map.get(c.author_user_id, f"#{c.author_user_id}")
                        ts = fmt_hm_tr(parse_iso_dt(c.created_at.isoformat()))
                        prefix = ">" * depth  # basit iç içe görünüm
                        st.markdown(f"{prefix} **_{who}_ — {ts}**  \n{prefix} {c.content}")

                        # ---- Yanıt hakkı: sadece rapor sahibi, admin hariç, ve KENDİ yorumuna değil ----
                        can_reply = (
                            current_uid == r.user_id
                            and current_role != ROLE_ADMIN
                            and c.author_user_id != current_uid
                        )

                        if can_reply:
                            with st.form(f"reply_{r.id}_{c.id}"):
                                reply_txt = st.text_area(
                                    "Yanıt",
                                    key=f"reply_txt_{r.id}_{c.id}",
                                    height=80,
                                    label_visibility="collapsed",
                                    placeholder="Bu yoruma yanıt yazın…",
                                )
                                ok = st.form_submit_button("↪️ Yanıtla")

                            if ok:
                                # Sunucu tarafı güvenlik: koşulları tekrar kontrol et
                                still_can = (
                                    current_uid == r.user_id
                                    and current_role != ROLE_ADMIN
                                    and c.author_user_id != current_uid
                                    and c.report_id == r.id
                                )
                                if not still_can:
                                    st.error("Bu yoruma yanıt verme yetkiniz yok.")
                                elif not (reply_txt or "").strip():
                                    st.error("Yanıt boş olamaz.")
                                else:
                                    db = SessionLocal()
                                    try:
                                        add_comment(
                                            db,
                                            report_id=r.id,
                                            author_user_id=current_uid,
                                            content=reply_txt,
                                            parent_comment_id=c.id,
                                        )
                                        st.success("Yanıt eklendi.")
                                    finally:
                                        db.close()
                                    st.rerun()
                else:
                    st.caption("Henüz yorum yok.")

    # ---------- Eksik raporlar bölümü
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
