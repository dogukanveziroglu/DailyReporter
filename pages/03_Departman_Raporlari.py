# pages/03_Departman_Raporlari.py
from __future__ import annotations
import streamlit as st
from datetime import date
from typing import List, Optional

from app.core.rbac import require_min_role, ROLE_USER, ROLE_ADMIN, ROLE_LEAD, ROLE_DEPT_LEAD
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments,
    list_user_ids_in_department,
    list_reports_for_department,
    list_comments_tree_by_report_ids,
    missing_reports_for_department_and_date,
    list_users_simple,
    add_comment,
)
from app.utils.dates import today_tr, fmt_hm_tr, parse_iso_dt
from app.ui.nav import build_sidebar

st.set_page_config(page_title="Departman Raporları", page_icon="🏢", initial_sidebar_state="expanded")
build_sidebar()

# Flash anahtarı (yorum sonrası başarı mesajı)
COMMENT_FLASH_KEY = "comment_saved_flash"

@require_min_role(ROLE_USER)
def page():
    st.title("🏢 Departman Raporları")

    # Flash mesajı (varsa göster ve temizle)
    if st.session_state.get(COMMENT_FLASH_KEY):
        st.success(st.session_state[COMMENT_FLASH_KEY])
        del st.session_state[COMMENT_FLASH_KEY]

    # Tüm departmanlar
    db = SessionLocal()
    try:
        deps = list_departments(db)
        users_all = list_users_simple(db)  # isim haritası için
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

    # Sadece tek tarih seçimi
    d: date = st.date_input("Tarih", value=today_tr())

    # Departmandaki kullanıcılar (çoktan-çoka)
    db = SessionLocal()
    try:
        user_ids: List[int] = list_user_ids_in_department(db, department_id=dep_id)
    finally:
        db.close()

    if not user_ids:
        st.info("Seçilen departmanda kullanıcı bulunmuyor.")
        return

    # İsim haritası
    name_map = {u.id: (u.full_name or u.username) for u in users_all}

    auth = st.session_state.get("auth") or {}
    current_uid: Optional[int] = auth.get("user_id")
    current_role = auth.get("role", "user")

    # ---------- Raporlar
    st.subheader("Raporlar")
    db = SessionLocal()
    try:
        reports = list_reports_for_department(db, department_id=dep_id, d=d)
        tree_map = list_comments_tree_by_report_ids(db, report_ids=[r.id for r in reports])
    finally:
        db.close()

    if not reports:
        st.info("Seçilen günde rapor bulunmuyor.")
    else:
        for r in reports:
            owner = name_map.get(r.user_id, f"#{r.user_id}")
            with st.expander(f"👤 {owner} · 📅 {r.date} · 🏷️ {r.project or '-'}", expanded=False):
                # Rapor içeriği
                st.markdown(r.content)

                # Yorumlar (herkes görebilir)
                cmts = tree_map.get(r.id, [])
                if cmts:
                    st.markdown("**Yorumlar**")
                    for c, depth in cmts:
                        who = name_map.get(c.author_user_id, f"#{c.author_user_id}")
                        ts = fmt_hm_tr(parse_iso_dt(c.created_at.isoformat()))
                        prefix = ">" * depth  # basit iç içe görünüm
                        st.markdown(f"{prefix} **_{who}_ — {ts}**  \n{prefix} {c.content}")

                        # ---- Yanıt hakkı: SADECE rapor sahibi; admin/lead/dept_lead yanıtlayamaz; kişi kendi yorumuna da yanıt yazamaz
                        can_reply = (
                            current_uid == r.user_id
                            and current_role not in (ROLE_ADMIN, ROLE_LEAD, ROLE_DEPT_LEAD)
                            and c.author_user_id != current_uid
                        )
                        if can_reply:
                            with st.form(f"reply_{r.id}_{c.id}"):
                                reply_txt = st.text_area(
                                    "Yanıt",
                                    key=f"reply_txt_{r.id}_{c.id}",
                                    height=90,
                                    label_visibility="collapsed",
                                    placeholder="Bu yoruma yanıt yazın…",
                                )
                                ok = st.form_submit_button("↪️ Yanıtla")
                            if ok:
                                still_ok = (
                                    current_uid == r.user_id
                                    and current_role not in (ROLE_ADMIN, ROLE_LEAD, ROLE_DEPT_LEAD)
                                    and c.author_user_id != current_uid
                                    and c.report_id == r.id
                                )
                                if not still_ok:
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
                                            content=reply_txt.strip(),
                                            parent_comment_id=c.id,
                                        )
                                    finally:
                                        db.close()
                                    # Flash bırak ve yenile
                                    st.session_state[COMMENT_FLASH_KEY] = "💬 Yorum eklendi."
                                    st.rerun()
                else:
                    st.caption("Henüz yorum yok.")

                st.divider()

                # ---- Üst seviye yorum: admin + lead + dept_lead
                can_top_comment = current_role in (ROLE_ADMIN, ROLE_LEAD, ROLE_DEPT_LEAD)
                if can_top_comment:
                    st.markdown("**Yeni yorum ekle (üst seviye)**")
                    with st.form(f"topc_{r.id}"):
                        txt = st.text_area(
                            "Yorum",
                            key=f"txt_{r.id}",
                            height=120,
                            placeholder="Üst seviye yorumunuzu yazın…",
                        )
                        ok = st.form_submit_button("Ekle")
                    if ok:
                        if not current_uid:
                            st.error("Oturum bilgisi bulunamadı.")
                        elif not (txt or "").strip():
                            st.error("Yorum boş olamaz.")
                        else:
                            db = SessionLocal()
                            try:
                                add_comment(
                                    db,
                                    report_id=r.id,
                                    author_user_id=current_uid,
                                    content=txt.strip(),
                                    parent_comment_id=None,  # sadece üst seviye
                                )
                            finally:
                                db.close()
                            # Flash bırak ve yenile
                            st.session_state[COMMENT_FLASH_KEY] = "💬 Yorum eklendi."
                            st.rerun()

    # ---------- Eksik raporlar (seçilen gün)
    st.divider()
    st.subheader("Eksik Raporlar (Seçilen Gün)")
    db = SessionLocal()
    try:
        missing_users = missing_reports_for_department_and_date(db, department_id=dep_id, d=d)
    finally:
        db.close()

    if not missing_users:
        st.success("Seçilen günde eksik rapor yok.")
    else:
        for u in missing_users:
            st.warning(f"• {name_map.get(u.id, u.username)}")

if __name__ == "__main__":
    page()
