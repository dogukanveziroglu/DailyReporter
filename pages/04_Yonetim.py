from __future__ import annotations
import streamlit as st
from sqlalchemy.exc import IntegrityError

from app.core.rbac import require_min_role, ROLE_ADMIN
from app.db.database import SessionLocal
from app.db.repository import (
    list_departments, create_department,
    list_teams, create_team, list_team_leads_by_team,
    list_users_simple, list_users_by_team, create_user,
    update_user_role_team_dept, reset_password_for_user, delete_user
)
from app.utils.text import make_username
from app.ui.nav import build_sidebar

st.set_page_config(page_title="Yönetim", page_icon="🛠️", initial_sidebar_state="expanded")
build_sidebar()

def _user_label(u) -> str:
    return f"{u.full_name or u.username}  •  @{u.username}  •  #{u.id}  •  {u.role}"

@require_min_role(ROLE_ADMIN)
def page():
    st.title("🛠️ Yönetim")

    # ---------------------------
    # DEPARTMANLAR
    # ---------------------------
    st.header("Departmanlar")
    db = SessionLocal()
    try:
        deps = list_departments(db)
    finally:
        db.close()

    if deps:
        st.table([{"ID": d.id, "Ad": d.name} for d in deps])

    with st.form("dep_new"):
        dn = st.text_input("Yeni departman adı")
        ok = st.form_submit_button("Ekle")

    if ok:
        name = (dn or "").strip()
        if not name:
            st.error("Departman adı boş olamaz.")
        else:
            if any((d.name or "").strip().lower() == name.lower() for d in deps):
                st.warning(f"“{name}” adında bir departman zaten var.")
            else:
                db = SessionLocal()
                try:
                    create_department(db, name=name)
                    st.success("Departman eklendi.")
                    st.rerun()
                except IntegrityError:
                    st.error(f"“{name}” adına sahip departman zaten mevcut.")
                except Exception as e:
                    st.error(f"Departman eklenemedi: {e}")
                finally:
                    db.close()

    st.divider()

    # ---------------------------
    # TAKIMLAR
    # ---------------------------
    st.header("Takımlar")
    db = SessionLocal()
    try:
        deps = list_departments(db)
        teams = list_teams(db)
    finally:
        db.close()

    if teams:
        rows = []
        db = SessionLocal()
        try:
            for t in teams:
                leads = list_team_leads_by_team(db, team_id=t.id)
                rows.append({
                    "ID": t.id,
                    "Ad": t.name,
                    "Departman": (t.department.name if t.department else "-"),
                    "Lider Sayısı": len(leads),
                })
        finally:
            db.close()
        st.table(rows)

    with st.form("team_new"):
        name = st.text_input("Takım adı")
        dep_id = st.selectbox(
            "Departman",
            options=[None] + [d.id for d in deps],
            format_func=lambda i: "-" if i is None else next(d.name for d in deps if d.id == i)
        )
        ok_team = st.form_submit_button("Takım Ekle")

    if ok_team:
        tname = (name or "").strip()
        if not tname:
            st.error("Takım adı boş olamaz.")
        else:
            if any(
                ((t.name or "").strip().lower() == tname.lower()) and (t.department.id if t.department else None) == dep_id
                for t in teams
            ):
                st.warning(f"Bu departmanda “{tname}” adlı bir takım zaten var.")
            else:
                db = SessionLocal()
                try:
                    create_team(db, name=tname, department_id=dep_id, lead_user_id=None)
                    st.success("Takım eklendi.")
                    st.rerun()
                except IntegrityError:
                    st.error("Takım eklenemedi: isim/bağlılık benzersiz olmalı.")
                except Exception as e:
                    st.error(f"Takım eklenemedi: {e}")
                finally:
                    db.close()

    st.divider()

    # ---------------------------
    # KULLANICILAR (Liste + satır içi SİL)
    # ---------------------------
    st.header("Kullanıcılar")

    if "del_candidate" not in st.session_state:
        st.session_state["del_candidate"] = None

    db = SessionLocal()
    try:
        users = list_users_simple(db)
        deps = list_departments(db)
        teams = list_teams(db)
    finally:
        db.close()

    if users:
        h = st.columns([0.5, 1.0, 1.4, 0.8, 1.0, 1.0, 0.5])
        h[0].markdown("**ID**")
        h[1].markdown("**Username**")
        h[2].markdown("**Ad Soyad**")
        h[3].markdown("**Rol**")
        h[4].markdown("**Departman**")
        h[5].markdown("**Takım**")
        h[6].markdown("**Sil**")

        for u in users:
            cols = st.columns([0.5, 1.0, 1.4, 0.8, 1.0, 1.0, 0.5])
            cols[0].write(u.id)
            cols[1].write(u.username)
            cols[2].write(u.full_name or "-")
            cols[3].write(u.role)
            cols[4].write(u.department.name if u.department else "-")
            cols[5].write(u.team.name if u.team else "-")
            with cols[6]:
                if st.button("❌ Sil", key=f"delbtn_{u.id}"):
                    st.session_state["del_candidate"] = u.id
                    st.rerun()
    else:
        st.info("Kayıtlı kullanıcı yok.")

    cand_id = st.session_state.get("del_candidate")
    if cand_id and users:
        target = next((x for x in users if x.id == cand_id), None)
        if target:
            st.warning(f"Silinecek: **{_user_label(target)}**")
            confirm_text = st.text_input("Onay için kullanıcı adını yazın", key="confirm_delete_text")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Evet, sil"):
                    me = st.session_state["auth"]["user_id"]
                    admin_count = sum(1 for u in users if u.role == "admin")

                    if confirm_text.strip() != target.username:
                        st.error("Onay metni hatalı. Kullanıcının **username** değerini yazmalısınız.")
                    elif cand_id == me:
                        st.error("Kendi hesabınızı silemezsiniz.")
                    elif target.role == "admin" and admin_count <= 1:
                        st.error("Son admin hesabı silinemez.")
                    else:
                        db = SessionLocal()
                        try:
                            delete_user(db, user_id=cand_id)
                            st.success("Kullanıcı silindi.")
                        except Exception as e:
                            st.error(f"Kullanıcı silinemedi: {e}")
                        finally:
                            db.close()
                        st.session_state["del_candidate"] = None
                        st.rerun()
            with c2:
                if st.button("Vazgeç"):
                    st.session_state["del_candidate"] = None
                    st.rerun()

    st.divider()

    # ---------------------------
    # YENİ KULLANICI
    # ---------------------------
    st.subheader("Yeni Kullanıcı")
    with st.form("user_new"):
        full = st.text_input("Ad Soyad")
        username_preview = make_username(full or "")
        st.caption(f"Otomatik username: `{username_preview}`")
        # ↓ BURADA dept_lead eklendi
        role = st.selectbox("Rol", options=["user", "team_lead", "dept_lead", "admin"])
        dep_id = st.selectbox(
            "Departman",
            options=[None] + [d.id for d in deps],
            format_func=lambda i: "-" if i is None else next(d.name for d in deps if d.id == i)
        )
        team_id = st.selectbox(
            "Takım",
            options=[None] + [t.id for t in teams],
            format_func=lambda i: "-" if i is None else next(t.name for t in teams if t.id == i)
        )
        password = st.text_input("Şifre", type="password", value="123456")
        ok_new = st.form_submit_button("Kullanıcı Oluştur")

    if ok_new:
        full_clean = (full or "").strip()
        if not full_clean:
            st.error("Ad Soyad gerekli.")
        else:
            if any(u.username.lower() == username_preview.lower() for u in users):
                st.warning(f"`{username_preview}` kullanıcı adı zaten kullanılıyor. Ad Soyad'ı değiştirin veya elle düzenleyin.")
            else:
                db = SessionLocal()
                try:
                    create_user(
                        db,
                        username=username_preview,
                        password=password or "123456",
                        full_name=full_clean,
                        role=role,
                        department_id=dep_id,
                        team_id=team_id,
                    )
                    st.success(f"Kullanıcı oluşturuldu: {username_preview}")
                    st.rerun()
                except IntegrityError:
                    st.error("Kullanıcı oluşturulamadı: username benzersiz olmalı.")
                except Exception as e:
                    st.error(f"Kullanıcı oluşturulamadı: {e}")
                finally:
                    db.close()

    # ---------------------------
    # KULLANICI GÜNCELLE / ROL ATAMA (dropdown)
    # ---------------------------
    st.subheader("Kullanıcı Güncelle / Rol Atama")
    if not users:
        st.info("Önce kullanıcı oluşturun.")
    else:
        user_map = {u.id: _user_label(u) for u in users}
        selected_uid = st.selectbox(
            "Kullanıcı",
            options=list(user_map.keys()),
            format_func=lambda i: user_map[i],
            key="edit_user_select",
        )
        # ↓ BURADA dept_lead eklendi
        role = st.selectbox("Yeni Rol", options=["user", "team_lead", "dept_lead", "admin"])
        dep_id = st.selectbox(
            "Yeni Departman",
            options=[None] + [d.id for d in deps],
            format_func=lambda i: "-" if i is None else next(d.name for d in deps if d.id == i),
            key="dep2"
        )
        team_id = st.selectbox(
            "Yeni Takım",
            options=[None] + [t.id for t in teams],
            format_func=lambda i: "-" if i is None else next(t.name for t in teams if t.id == i),
            key="team2"
        )
        if st.button("Güncelle"):
            db = SessionLocal()
            try:
                update_user_role_team_dept(db, user_id=selected_uid, role=role, department_id=dep_id, team_id=team_id)
                st.success("Güncellendi.")
            except Exception as e:
                st.error(f"Güncellenemedi: {e}")
            finally:
                db.close()
            st.rerun()

    # ---------------------------
    # PAROLA SIFIRLAMA (dropdown)
    # ---------------------------
    st.subheader("Parola Sıfırlama")
    if not users:
        st.info("Önce kullanıcı oluşturun.")
    else:
        user_map2 = {u.id: _user_label(u) for u in users}
        selected_uid2 = st.selectbox(
            "Kullanıcı",
            options=list(user_map2.keys()),
            format_func=lambda i: user_map2[i],
            key="pwd_user_select",
        )
        newp = st.text_input("Yeni Şifre", type="password")
        if st.button("Sıfırla"):
            if not newp:
                st.error("Yeni şifre girin.")
            else:
                db = SessionLocal()
                try:
                    reset_password_for_user(db, user_id=selected_uid2, new_password=newp)
                    st.success("Parola sıfırlandı.")
                except Exception as e:
                    st.error(f"Parola sıfırlanamadı: {e}")
                finally:
                    db.close()

if __name__ == "__main__":
    page()
