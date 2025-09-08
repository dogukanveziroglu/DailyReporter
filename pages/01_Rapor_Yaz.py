# pages/01_Rapor_Yaz.py
from __future__ import annotations
import streamlit as st
from datetime import date

from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments_for_user,
    get_report_by_user_dept_date,
    upsert_report,
)
from app.ui.nav import build_sidebar
from app.utils.dates import today_tr

st.set_page_config(page_title="Rapor Yaz", page_icon="📝", initial_sidebar_state="expanded")
build_sidebar()

FLASH_KEY = "report_saved_flash"

@require_min_role(ROLE_USER)
def page():
    st.title("📝 Rapor Yaz")

    # Flash mesajı (varsa göster)
    if st.session_state.get(FLASH_KEY):
        st.success(st.session_state[FLASH_KEY])
        del st.session_state[FLASH_KEY]

    auth = st.session_state["auth"]
    uid = auth["user_id"]

    # Kullanıcının bağlı olduğu departmanlar
    db = SessionLocal()
    try:
        my_deps = list_departments_for_user(db, user_id=uid)
    finally:
        db.close()

    if not my_deps:
        st.info("Herhangi bir departmana atanmadığınız için rapor girişi yapamazsınız. Lütfen yöneticinize bildirin.")
        return

    dep_id = st.selectbox(
        "Departman",
        options=[d.id for d in my_deps],
        format_func=lambda i: next(d.name for d in my_deps if d.id == i),
    )

    # Varsayılan: bugünün raporu
    d: date = st.date_input("Tarih", value=today_tr())

    # Varsa mevcut raporu çekip formu dolduralım
    db = SessionLocal()
    try:
        existing = get_report_by_user_dept_date(db, user_id=uid, department_id=dep_id, d=d)
    finally:
        db.close()

    st.subheader("Günlük Çalışma Notları")
    with st.form("report_form", clear_on_submit=False):
        project = st.text_input("Proje/Etiket (opsiyonel)", value=(existing.project if existing else ""))
        content = st.text_area(
            "Rapor",
            value=(existing.content if existing else ""),
            height=260,
            placeholder="- Bugün yaptıklarım...\n- Yarın planım...\n- Engeller/Notlar..."
        )
        ok = st.form_submit_button("Kaydet")

    if ok:
        if not (content or "").strip():
            st.error("Rapor içeriği boş olamaz.")
            return
        db = SessionLocal()
        try:
            upsert_report(
                db,
                user_id=uid,
                department_id=dep_id,
                d=d,
                content=content.strip(),
                project=(project or None),
                tags_json=None,
            )
        finally:
            db.close()
        # Flash mesajını bırak, sonra yenile
        st.session_state[FLASH_KEY] = "✅ Rapor kaydedildi."
        st.rerun()

if __name__ == "__main__":
    page()
