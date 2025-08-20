from __future__ import annotations
import streamlit as st

def labeled_text(label:str, key:str, value:str=""):
    return st.text_input(label, value=value, key=key)

def labeled_password(label:str, key:str):
    return st.text_input(label, type="password", key=key)
