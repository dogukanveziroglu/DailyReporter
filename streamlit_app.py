from __future__ import annotations
import streamlit as st

from app.db.seed import create_tables, ensure_admin, ensure_dirs
from app.db.database import SessionLocal
from app.db.repository import authenticate_user, get_user_by_username, change_password
from app.core.rbac import role_weight, ROLE_USER, ROLE_ADMIN
from app.utils.dates import today_tr
from app.ui.nav import build_sidebar
from app.db.migrations import safe_run_migrations  # ← Tek seferlik migration

st.set_page_config(
    page_title="Günlük Raporlama",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---- Veritabanı / dizinler / seed ve tek seferlik migration ----
create_tables()
ensure_dirs()
ensure_admin()
safe_run_migrations()


def login_form():
    st.header("🔐 Giriş Yap")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Kullanıcı adı", placeholder="ör. isminsoyisim")
        password = st.text_input("Şifre", type="password")
        ok = st.form_submit_button("Giriş")
    if ok:
        if not username or not password:
            st.error("Kullanıcı adı ve şifre gerekli.")
            return
        db = SessionLocal()
        try:
            user = authenticate_user(db, username=username, password=password)
        finally:
            db.close()
        if not user:
            st.error("Hatalı bilgiler.")
            return
        st.session_state["auth"] = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name or user.username,
        }
        st.success("Giriş başarılı.")
        st.rerun()


def home():
    auth = st.session_state["auth"]
    st.success(f"Merhaba, {auth['full_name']} 👋")
    st.write("Bugün:", today_tr())

    # Profil: Şifre Değiştir
    with st.expander("🔑 Şifremi Değiştir", expanded=False):
        with st.form("pwd_change_form", clear_on_submit=False):
            old = st.text_input("Mevcut Şifre", type="password")
            new1 = st.text_input("Yeni Şifre", type="password")
            new2 = st.text_input("Yeni Şifre (tekrar)", type="password")
            ok = st.form_submit_button("Güncelle")
        if ok:
            if not old or not new1 or not new2:
                st.error("Tüm alanları doldurun.")
            elif len(new1) < 6:
                st.error("Yeni şifre en az 6 karakter olmalı.")
            elif new1 != new2:
                st.error("Yeni şifreler eşleşmiyor.")
            else:
                db = SessionLocal()
                try:
                    changed = change_password(
                        db, user_id=auth["user_id"], old_password=old, new_password=new1
                    )
                finally:
                    db.close()
                if changed:
                    st.success("Şifreniz güncellendi ✔")
                else:
                    st.error("Mevcut şifre yanlış.")

    st.info("Soldaki menüden sayfalara geçebilirsiniz.")


def main():
    # Yan menü (rol bazlı görünürlük, nav.py içinde)
    build_sidebar()

    if "auth" not in st.session_state:
        login_form()
    else:
        # Kullanıcının hâlâ var olduğunu/rolünü doğrula
        db = SessionLocal()
        try:
            u = get_user_by_username(db, st.session_state["auth"]["username"])
            if not u:
                st.error("Kullanıcı bulunamadı.")
                st.stop()
            st.session_state["auth"]["role"] = u.role
            st.session_state["auth"]["full_name"] = u.full_name or u.username
        finally:
            db.close()
        home()


if __name__ == "__main__":
    main()
