from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="Çıkış", page_icon="🚪")
st.title("🚪 Çıkış")
if "auth" in st.session_state:
    st.info(f"{st.session_state['auth']['username']} çıkış yaptı.")
    del st.session_state["auth"]
st.link_button("Giriş ekranına dön", "./")
