from __future__ import annotations
import streamlit as st
from datetime import date
from typing import List, Optional

from app.core.rbac import require_min_role, ROLE_ADMIN
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments,
    list_user_ids_in_department,
    list_reports_for_department,
    list_users_simple,
    list_comments_tree_by_report_ids,
    add_comment,
)
from app.utils.dates import today_tr, fmt_hm_tr, parse_iso_dt
from app.ui.nav import build_sidebar

st.set_page_config(page_title="Rapor Yorumları", page_icon="🗨️", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_ADMIN)
def page():
    st.title("🗨️ Rapor Yorumları (Admin)")

    # Ortak veriler
    db = SessionLocal()
    try:
        deps = list_departments(db)
        users_all = list_users_simple(db)  # isim haritası için
    finally:
        db.close()

    if not deps:
        st.info("Önce departman oluşturun.")
        return

    dep_id = st.selectbox(
        "Departman",
        options=[d.id for d in deps],
        format_func=lambda i: next(d.name for d in deps if d.id == i),
    )
    d: date = st.date_input("Tarih", value=today_tr())

    # Departmandaki kullanıcı kimlikleri (çoktan-çoka)
    db = SessionLocal()
    try:
        user_ids: List[int] = list_user_ids_in_department(db, department_id=dep_id)
    finally:
        db.close()

    if not user_ids:
        st.info("Bu departmanda kullanıcı yok.")
        return

    name_map = {u.id: (u.full_name or u.username) for u in users_all}

    # Raporları getir (departman + gün)
    db = SessionLocal()
    try:
        reports = list_reports_for_department(db, department_id=dep_id, d=d)
        tree_map = list_comments_tree_by_report_ids(db, report_ids=[r.id for r in reports])
    finally:
        db.close()

    if not reports:
        st.info("Seçilen günde rapor yok.")
        return

    for r in reports:
        owner = name_map.get(r.user_id, f"#{r.user_id}")
        with st.expander(f"👤 {owner} · 📅 {r.date} · 🏷️ {r.project or '-'}", expanded=False):
            st.markdown(r.content)

            # Mevcut yorumlar (okuma)
            cmts = tree_map.get(r.id, [])
            st.markdown("**Yorumlar**")
            if not cmts:
                st.caption("Henüz yorum yok.")
            else:
                for c, depth in cmts:
                    who = name_map.get(c.author_user_id, f"#{c.author_user_id}")
                    ts = fmt_hm_tr(parse_iso_dt(c.created_at.isoformat()))
                    prefix = ">" * depth
                    st.markdown(f"{prefix} **_{who}_ — {ts}**  \n{prefix} {c.content}")

            st.divider()
            # SADECE ÜST SEVİYE YORUM (admin)
            st.markdown("**Yeni yorum ekle (üst seviye)**")
            with st.form(f"cmt_{r.id}"):
                txt = st.text_area("Yorum", key=f"txt_{r.id}", height=120, placeholder="Yalnızca üst seviye yorum eklenir.")
                ok = st.form_submit_button("Ekle")
            if ok:
                if not (txt or "").strip():
                    st.error("Yorum boş olamaz.")
                else:
                    db = SessionLocal()
                    try:
                        add_comment(
                            db,
                            report_id=r.id,
                            author_user_id=st.session_state["auth"]["user_id"],
                            content=txt.strip(),
                            parent_comment_id=None,  # yanıt yok
                        )
                        st.success("Yorum eklendi.")
                    finally:
                        db.close()
                    st.rerun()

if __name__ == "__main__":
    page()
