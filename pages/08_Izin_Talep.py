from __future__ import annotations
import streamlit as st
from datetime import date
from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import create_leave, list_leaves_for_user, delete_leave
from app.ui.nav import build_sidebar
from app.utils.dates import today_tr

st.set_page_config(page_title="İzin Talebi", page_icon="🗓️", initial_sidebar_state="expanded")
build_sidebar()

@require_min_role(ROLE_USER)
def page():
    st.title("🗓️ İzin Talebi")

    auth = st.session_state["auth"]
    uid = auth["user_id"]

    st.subheader("Yeni İzin")
    with st.form("leave_new", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Başlangıç", value=today_tr())
        with c2:
            end = st.date_input("Bitiş", value=today_tr())
        reason = st.text_area("Mazeret (sadece sen ve yöneticiler görür)", height=90, placeholder="Örn: Sağlık, aile, resmi işler…")
        ok = st.form_submit_button("Kaydet")
    if ok:
        if start > end:
            st.error("Başlangıç tarihi bitişten büyük olamaz.")
        else:
            db = SessionLocal()
            try:
                create_leave(db, user_id=uid, start_date=start, end_date=end, reason=reason.strip() or None)
                st.success("İzin talebiniz eklendi.")
            finally:
                db.close()
            st.rerun()

    st.divider()
    st.subheader("İzinlerim")
    db = SessionLocal()
    try:
        my_leaves = list_leaves_for_user(db, user_id=uid)
    finally:
        db.close()

    if not my_leaves:
        st.info("Kayıtlı izniniz yok.")
    else:
        for lv in my_leaves:
            with st.container(border=True):
                st.write(f"📅 **{lv.start_date} → {lv.end_date}**  \n📝 _Mazeret (sadece siz ve yöneticiler görür):_ {lv.reason or '-'}")
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Sil", key=f"del_{lv.id}"):
                        db = SessionLocal()
                        try:
                            if delete_leave(db, leave_id=lv.id, user_id=uid, as_admin=False):
                                st.success("Silindi.")
                            else:
                                st.error("Silme yetkiniz yok.")
                        finally:
                            db.close()
                        st.rerun()

if __name__ == "__main__":
    page()
