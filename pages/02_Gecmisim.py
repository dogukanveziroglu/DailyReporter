from __future__ import annotations
import json
import streamlit as st
from app.core.rbac import require_min_role, ROLE_USER
from app.db.database import SessionLocal
from app.db.repository import list_user_reports, create_report_revision
from app.utils.dates import today_tr, now_tr, fmt_hm_tr, daterange_days, parse_iso_dt
from app.ui.nav import build_sidebar  # ← ek

st.set_page_config(page_title="Geçmişim", page_icon="📚", initial_sidebar_state="expanded")
build_sidebar()  # ← ek

@require_min_role(ROLE_USER)
def page():
    st.title("📚 Geçmişim")

    auth = st.session_state["auth"]
    uid = auth["user_id"]

    # ---- Görüntüleme filtresi: Son N gün
    c1, c2 = st.columns([1, 2])
    with c1:
        days = st.number_input("Gün", min_value=1, max_value=60, value=7, help="Son kaç gün görüntülensin?")
    with c2:
        q = st.text_input("Arama (metin/proje)", placeholder="örn. sprint, müşteri, hata...")

    start_d, end_d = daterange_days(int(days))

    # ---- Kayıtları getir
    db = SessionLocal()
    try:
        reports = list_user_reports(db, user_id=uid, start=start_d, end=end_d, q=q or None)
    finally:
        db.close()

    if not reports:
        st.info("Seçilen aralıkta rapor bulunmuyor.")
        return

    today = today_tr()

    # ---- Listele
    for r in reports:
        # 'değişmiş' etiketi ve saati
        edited_label = ""
        if r.tags_json:
            try:
                t = json.loads(r.tags_json)
                if isinstance(t, dict) and t.get("edited"):
                    hm = "-"
                    if t.get("edited_at"):
                        try:
                            hm = fmt_hm_tr(parse_iso_dt(t["edited_at"]))
                        except Exception:
                            pass
                    edited_label = f" (değişmiş • {hm})"
            except Exception:
                pass

        header = f"📅 {r.date}{edited_label} · 🏷️ {r.project or '-'}"
        with st.expander(header, expanded=False):
            st.markdown(r.content)

            # Sadece bugünün raporu düzenlenebilir
            if r.date == today:
                st.info("Bu raporu düzenlerseniz mevcut kayıt korunur; **yeni bir 'değişmiş' kayıt** oluşturulur.")
                with st.form(f"edit_{r.id}"):
                    new_project = st.text_input("Proje", value=r.project or "")
                    new_content = st.text_area("İçerik", value=r.content, height=220)
                    ok = st.form_submit_button("Kaydet (Yeni Değişiklik Kaydı)")

                if ok:
                    if not (new_content or "").strip():
                        st.error("İçerik boş olamaz.")
                    else:
                        db = SessionLocal()
                        try:
                            edited_at = now_tr().isoformat()
                            create_report_revision(
                                db,
                                user_id=uid,
                                d=today,
                                content=new_content.strip(),
                                project=(new_project or None),
                                edited_at_iso=edited_at,
                            )
                            st.success(f"Değişiklik kaydedildi. (İstanbul saati {fmt_hm_tr(parse_iso_dt(edited_at))})")
                        finally:
                            db.close()
                        st.rerun()
            else:
                st.caption("✋ Bu kayıt geçmiş tarihlidir. Düzenleme yalnızca bugüne aittir.")

if __name__ == "__main__":
    page()
