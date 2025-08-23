from __future__ import annotations
import streamlit as st
from datetime import date
from typing import Optional

from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import (
    create_todo, list_todos_for_user, update_todo, toggle_todo_done, delete_todo
)
from app.ui.nav import build_sidebar
from app.utils.dates import today_tr

st.set_page_config(page_title="Görevlerim (To-Do)", page_icon="✅", initial_sidebar_state="expanded")
build_sidebar()

PRIORITY_MAP = {
    "Düşük": 1,
    "Normal": 2,
    "Yüksek": 3,
}
PRIORITY_REV = {v: k for k, v in PRIORITY_MAP.items()}

@require_min_role(ROLE_USER)
def page():
    st.title("✅ Görevlerim (To-Do)")

    auth = st.session_state["auth"]
    uid = auth["user_id"]

    # --- Yeni görev formu
    st.subheader("Yeni Görev")
    with st.form("new_todo", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input("Başlık", placeholder="Görev başlığı", max_chars=200)
        with c2:
            prio_label = st.selectbox("Öncelik", list(PRIORITY_MAP.keys()), index=1)
        desc = st.text_area("Açıklama", placeholder="İsteğe bağlı notlar…", height=100)
        due: Optional[date] = st.date_input("Bitiş Tarihi (opsiyonel)", value=None)
        ok = st.form_submit_button("Ekle")
    if ok:
        if not (title or "").strip():
            st.error("Başlık boş olamaz.")
        else:
            db = SessionLocal()
            try:
                create_todo(
                    db,
                    user_id=uid,
                    title=title.strip(),
                    description=(desc or None),
                    due_date=due,
                    priority=PRIORITY_MAP[prio_label],
                )
                st.success("Görev eklendi.")
            finally:
                db.close()
            st.rerun()

    st.divider()

    # --- Filtreler
    st.subheader("Görevlerim")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Arama", placeholder="başlık/açıklama içinde ara…")
    with c2:
        show_done = st.selectbox("Durum", ["Tümü", "Açık", "Tamamlandı"], index=1)
    with c3:
        only_overdue = st.checkbox("Sadece gecikenler", value=False)

    show_done_flag = None
    if show_done == "Açık":
        show_done_flag = False
    elif show_done == "Tamamlandı":
        show_done_flag = True

    # --- Liste
    db = SessionLocal()
    try:
        todos = list_todos_for_user(
            db,
            user_id=uid,
            show_done=show_done_flag,
            search=(q or None),
            only_overdue=only_overdue,
        )
    finally:
        db.close()

    if not todos:
        st.info("Kriterlere uyan görev bulunamadı.")
        return

    # Açık ve tamamlanmışları iki bölümde gösterelim (kullanıcı seçse bile)
    today = today_tr()
    open_todos = [t for t in todos if not t.is_done]
    done_todos = [t for t in todos if t.is_done]

    if open_todos:
        st.markdown("### ⏳ Açık Görevler")
        for t in open_todos:
            overdue = (t.due_date is not None and t.due_date < today)
            with st.container(border=True):
                c1, c2 = st.columns([0.12, 0.88])
                with c1:
                    chk = st.checkbox(" ", key=f"done_{t.id}", value=False)
                with c2:
                    header = f"**{t.title}**"
                    if overdue:
                        header += "  \n:warning: _Gecikmiş_"
                    if t.due_date:
                        header += f"  \n🗓️ Son tarih: {t.due_date}"
                    header += f"  \n🏷️ Öncelik: **{PRIORITY_REV.get(t.priority, 'Normal')}**"
                    st.markdown(header)
                    if t.description:
                        st.caption(t.description)

                    # İşlemler
                    with st.expander("Düzenle / Sil", expanded=False):
                        with st.form(f"edit_{t.id}"):
                            e_title = st.text_input("Başlık", value=t.title, max_chars=200)
                            e_desc = st.text_area("Açıklama", value=t.description or "", height=100)
                            e_due = st.date_input("Bitiş Tarihi (opsiyonel)", value=t.due_date)
                            e_prio = st.selectbox(
                                "Öncelik", list(PRIORITY_MAP.keys()),
                                index={1:0,2:1,3:2}.get(t.priority,1)
                            )
                            colb1, colb2, colb3 = st.columns([1,1,2])
                            save = colb1.form_submit_button("Kaydet")
                            delbtn = colb2.form_submit_button("Sil")
                        if save:
                            db = SessionLocal()
                            try:
                                update_todo(
                                    db,
                                    todo_id=t.id, user_id=uid,
                                    title=e_title, description=e_desc,
                                    due_date=e_due, priority=PRIORITY_MAP[e_prio]
                                )
                                st.success("Güncellendi.")
                            finally:
                                db.close()
                            st.rerun()
                        if delbtn:
                            db = SessionLocal()
                            try:
                                if delete_todo(db, todo_id=t.id, user_id=uid):
                                    st.success("Silindi.")
                                else:
                                    st.error("Silme yetkisi yok veya kayıt bulunamadı.")
                            finally:
                                db.close()
                            st.rerun()

                # Checkbox action (tamamla)
                if chk:
                    db = SessionLocal()
                    try:
                        toggle_todo_done(db, todo_id=t.id, user_id=uid, done=True)
                    finally:
                        db.close()
                    st.rerun()
    else:
        st.caption("Açık görev bulunmuyor.")

    st.divider()

    with st.expander(f"✅ Tamamlananlar ({len(done_todos)})", expanded=False):
        for t in done_todos:
            with st.container(border=True):
                c1, c2 = st.columns([0.12, 0.88])
                with c1:
                    chk = st.checkbox(" ", key=f"undone_{t.id}", value=True)
                with c2:
                    header = f"**{t.title}**"
                    if t.due_date:
                        header += f"  \n🗓️ Son tarih: {t.due_date}"
                    header += f"  \n🏷️ Öncelik: **{PRIORITY_REV.get(t.priority, 'Normal')}**"
                    st.markdown(header)
                    if t.description:
                        st.caption(t.description)
                # Checkbox action (geri al)
                if not chk:
                    db = SessionLocal()
                    try:
                        toggle_todo_done(db, todo_id=t.id, user_id=uid, done=False)
                    finally:
                        db.close()
                    st.rerun()

if __name__ == "__main__":
    page()
