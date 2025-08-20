from __future__ import annotations
import streamlit as st
from datetime import timedelta
from app.utils.dates import today_tr

def daterange_filter(default_days:int=7):
    t=today_tr()
    c1,c2,c3=st.columns([1,1,1])
    with c1: start=st.date_input("Başlangıç", value=t-timedelta(days=default_days))
    with c2: end=st.date_input("Bitiş", value=t)
    with c3:
        preset=st.selectbox("Aralık", ["7","14","30"], index=0)
        if preset=="7": start=t-timedelta(days=7)
        elif preset=="14": start=t-timedelta(days=14)
        else: start=t-timedelta(days=30)
    return start,end
