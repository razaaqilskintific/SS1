"""Reusable UI pieces: page chrome, pagination, small helpers."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config.settings import APP_NAME

_CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
h1, h2, h3 {color: #23272F; font-weight: 600; letter-spacing: -0.01em;}
[data-testid="stMetric"] {background: #F4F5F7; border: 1px solid #E3E5E9; padding: 14px 18px; border-radius: 10px;}
[data-testid="stMetricLabel"] {color: #5B6270;}
[data-testid="stSidebar"] {background: #F4F5F7;}
.small-note {color: #5B6270; font-size: 0.85rem;}
</style>
"""


def page_setup(title: str, icon: str = "📊") -> None:
    st.set_page_config(page_title=f"{title} · {APP_NAME}", page_icon=icon, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(f"**{APP_NAME}**")
        st.date_input("Tanggal proses", value=dt.date.today(), key="run_date", format="DD/MM/YYYY",
                      help="Dipakai untuk memeriksa tanggal mendatang dan 'bukan bulan berjalan'.")


def page_header(title: str, subtitle: str = "") -> None:
    st.title(title)
    if subtitle:
        st.markdown(f'<p class="small-note">{subtitle}</p>', unsafe_allow_html=True)


def paged(df: pd.DataFrame, key: str, column_config: dict | None = None, default_size: int = 100) -> None:
    n = len(df)
    c1, c2, _ = st.columns([1, 1, 4])
    sizes = [50, 100, 250, 500]
    size = c1.selectbox("Baris per halaman", sizes, index=sizes.index(default_size), key=f"{key}_size")
    pages = max(1, -(-n // size))
    page = c2.number_input("Halaman", min_value=1, max_value=pages, value=1, step=1, key=f"{key}_page")
    a = (int(page) - 1) * size
    st.caption(f"Menampilkan {a + 1 if n else 0:,}–{min(a + size, n):,} dari {n:,} baris")
    st.dataframe(df.iloc[a:a + size], width="stretch", hide_index=True, column_config=column_config or {})


def fmt_int(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v)
