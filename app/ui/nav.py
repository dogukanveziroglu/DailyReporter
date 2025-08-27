from __future__ import annotations
import streamlit as st
from app.core.rbac import role_weight, ROLE_ADMIN

def build_sidebar():
    st.sidebar.title("📒 Menü")
    auth = st.session_state.get("auth")
    role = (auth or {}).get("role", "")

    st.sidebar.page_link("streamlit_app.py", label="🏠 Ana Sayfa")
    st.sidebar.page_link("pages/01_Rapor_Yaz.py", label="📝 Rapor Yaz")
    st.sidebar.page_link("pages/02_Gecmisim.py", label="📚 Geçmişim")
    st.sidebar.page_link("pages/03_Departman_Raporlari.py", label="🏢 Departman Raporları")
    st.sidebar.page_link("pages/07_Gorevlerim_Todo.py", label="✅ Görevlerim (To-Do)")
    st.sidebar.page_link("pages/08_Izin_Talep.py", label="🗓️ İzin Talebi")

    if role_weight(role) >= role_weight(ROLE_ADMIN):
        st.sidebar.markdown("---")
        st.sidebar.page_link("pages/06_Rapor_Yorumlari.py", label="🗨️ Rapor Yorumları")
        st.sidebar.page_link("pages/05_Raporlama_Istatistik.py", label="📊 Raporlama & İstatistik")
        st.sidebar.page_link("pages/04_Yonetim.py", label="🛠️ Yönetim")
        st.sidebar.page_link("pages/09_Izinler_Admin.py", label="🗓️ İzinler")

    st.sidebar.markdown("---")
    st.sidebar.page_link("pages/99_Cikis.py", label="🚪 Çıkış")
