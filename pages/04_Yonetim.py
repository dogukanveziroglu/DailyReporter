from __future__ import annotations
import streamlit as st
from sqlalchemy.exc import IntegrityError

from app.core.rbac import require_min_role, ROLE_ADMIN
from app.db.database import SessionLocal
from app.db.repository import (
    # Departmanlar
    list_departments, create_department,
    # Takımlar
    list_teams, create_team,
    # Kullanıcılar
    list_users_simple, create_user, delete_user,
    update_user_role_team, set_user_departments, reset_password_for_user,
)
from app.ui.nav import build_sidebar
from app.utils.text import make_username

st.set_page_config(page_title="Yönetim", page_icon="🛠️", initial_sidebar_state="expanded")
build_sidebar()

ROLES = ["user", "lead", "dept_lead", "admin"]  # ← dept_lead eklendi

@require_min_role(ROLE_ADMIN)
def page():
    st.title("🛠️ Yönetim")

    # --- Ortak veriler
    db = SessionLocal()
    try:
        deps = list_departments(db)
        teams = list_teams(db)
        users = list_users_simple(db)
    finally:
        db.close()

    dep_id_to_name = {d.id: d.name for d in deps}
    team_id_to_name = {t.id: t.name for t in teams}

    st.subheader("📁 Departman Yönetimi")
    c1, c2 = st.columns([2, 3])
    with c1:
        with st.form("dep_add_form", clear_on_submit=True):
            dn = st.text_input("Yeni Departman Adı")
            ok = st.form_submit_button("Ekle")
        if ok:
            if not (dn or "").strip():
                st.error("Departman adı boş olamaz.")
            else:
                db = SessionLocal()
                try:
                    create_department(db, name=dn.strip())
                    st.success("Departman eklendi.")
                except IntegrityError:
                    db.rollback()
                    st.error("Bu isimde bir departman zaten var.")
                finally:
                    db.close()
                st.rerun()
    with c2:
        if deps:
            st.write("Mevcut Departmanlar:")
            for d in deps:
                st.write(f"• {d.name}")
        else:
            st.info("Henüz departman yok.")

    st.divider()
    st.subheader("👥 Kullanıcı Yönetimi")

    tabs = st.tabs(["➕ Kullanıcı Ekle", "✏️ Kullanıcı Güncelle", "🗑️ Kullanıcı Sil", "🔑 Şifre Sıfırla", "📋 Kullanıcı Listesi"])

    # ---------- Kullanıcı Ekle ----------
    with tabs[0]:
        st.markdown("Yeni kullanıcı eklerken birden fazla departman seçebilirsiniz.")
        with st.form("user_add_form", clear_on_submit=True):
            full = st.text_input("Ad Soyad", placeholder="Örn: İsim Soyisim")
            username_preview = make_username(full or "")
            st.caption(f"Önerilen kullanıcı adı: **{username_preview}** (gerekirse değiştirebilirsiniz)")
            username = st.text_input("Kullanıcı Adı", value=username_preview, help="Girişte kullanılacak, benzersiz olmalı.")
            pwd = st.text_input("Geçici Şifre", type="password")
            role = st.selectbox("Rol", options=ROLES, index=0)  # ← burada da dept_lead var
            # çoklu departman seçimi
            dep_ids = st.multiselect(
                "Departmanlar",
                options=[d.id for d in deps],
                format_func=lambda i: dep_id_to_name.get(i, f"#{i}")
            )
            team_opt = ["(yok)"] + [t.name for t in teams]
            team_choice = st.selectbox("Takım (opsiyonel)", options=team_opt, index=0)
            ok = st.form_submit_button("Ekle")

        if ok:
            if not username or not pwd:
                st.error("Kullanıcı adı ve şifre gerekli.")
            else:
                db = SessionLocal()
                try:
                    team_id = None if team_choice == "(yok)" else next((t.id for t in teams if t.name == team_choice), None)
                    u = create_user(
                        db,
                        username=username.strip(),
                        password=pwd,
                        full_name=(full or "").strip() or None,
                        role=role,
                        department_ids=dep_ids,
                        team_id=team_id,
                    )
                    st.success(f"Kullanıcı oluşturuldu: **{u.full_name or u.username}**")
                except IntegrityError as e:
                    db.rollback()
                    if "UNIQUE constraint failed: users.username" in str(e):
                        st.error("Bu kullanıcı adı zaten kullanımda.")
                    else:
                        st.error("Kullanıcı oluşturulamadı.")
                finally:
                    db.close()
                st.rerun()

    # ---------- Kullanıcı Güncelle ----------
    with tabs[1]:
        if not users:
            st.info("Güncellenecek kullanıcı yok.")
        else:
            # kullanıcı seç
            u_opts = {f"{(u.full_name or u.username)} (@{u.username})": u.id for u in users}
            sel_label = st.selectbox("Kullanıcı", options=list(u_opts.keys()))
            sel_uid = u_opts[sel_label]
            sel_user = next(u for u in users if u.id == sel_uid)

            st.caption(f"Seçili kullanıcı: **{sel_user.full_name or sel_user.username}**  | Rol: **{sel_user.role}**")

            # rol (güvenli index)
            try:
                role_index = ROLES.index(sel_user.role)
            except ValueError:
                role_index = 0  # bilinmeyen bir rol gelirse 'user' göster
            new_role = st.selectbox("Rol", options=ROLES, index=role_index)

            # takım
            team_opt2 = ["(yok)"] + [t.name for t in teams]
            current_team_name = team_id_to_name.get(sel_user.team.id, "(yok)") if getattr(sel_user, "team", None) else "(yok)"
            new_team_name = st.selectbox("Takım", options=team_opt2, index=team_opt2.index(current_team_name))
            new_team_id = None if new_team_name == "(yok)" else next((t.id for t in teams if t.name == new_team_name), None)

            # departman multiselect (çoklu)
            current_dep_ids = [d.id for d in (sel_user.departments or [])]
            new_dep_ids = st.multiselect(
                "Departmanlar",
                options=[d.id for d in deps],
                default=current_dep_ids,
                format_func=lambda i: dep_id_to_name.get(i, f"#{i}")
            )

            if st.button("Kaydet"):
                db = SessionLocal()
                try:
                    update_user_role_team(db, user_id=sel_uid, role=new_role, team_id=new_team_id)
                    set_user_departments(db, user_id=sel_uid, department_ids=new_dep_ids)
                    st.success("Kullanıcı güncellendi.")
                finally:
                    db.close()
                st.rerun()

    # ---------- Kullanıcı Sil ----------
    with tabs[2]:
        if not users:
            st.info("Silinecek kullanıcı yok.")
        else:
            u_opts2 = {f"{(u.full_name or u.username)} (@{u.username})": u.id for u in users}
            del_label = st.selectbox("Silinecek kullanıcı", options=list(u_opts2.keys()), key="del_user_sel")
            del_uid = u_opts2[del_label]
            warn = st.checkbox("Eminim, bu kullanıcı silinsin.", value=False)
            if st.button("Sil", type="primary", disabled=not warn):
                db = SessionLocal()
                try:
                    delete_user(db, user_id=del_uid)
                    st.success("Kullanıcı silindi.")
                finally:
                    db.close()
                st.rerun()

    # ---------- Şifre Sıfırla ----------
    with tabs[3]:
        if not users:
            st.info("Kullanıcı yok.")
        else:
            u_opts3 = {f"{(u.full_name or u.username)} (@{u.username})": u.id for u in users}
            pw_label = st.selectbox("Kullanıcı", options=list(u_opts3.keys()), key="pw_user_sel")
            pw_uid = u_opts3[pw_label]
            new_pwd = st.text_input("Yeni Şifre", type="password")
            if st.button("Şifreyi Sıfırla"):
                if not new_pwd or len(new_pwd) < 6:
                    st.error("Şifre en az 6 karakter olmalı.")
                else:
                    db = SessionLocal()
                    try:
                        reset_password_for_user(db, user_id=pw_uid, new_password=new_pwd)
                        st.success("Şifre güncellendi.")
                    finally:
                        db.close()
                    st.rerun()

    # ---------- Liste ----------
    with tabs[4]:
        if not users:
            st.info("Kullanıcı yok.")
        else:
            st.write("Mevcut kullanıcılar:")
            for u in users:
                dept_names = ", ".join([d.name for d in (u.departments or [])]) or "-"
                team_name = (u.team.name if getattr(u, "team", None) else "-")
                st.write(f"• **{u.full_name or u.username}** (@{u.username})  —  Rol: **{u.role}**,  Departmanlar: {dept_names},  Takım: {team_name}")

if __name__ == "__main__":
    page()
