"""Reusable UI pieces: page chrome, banner, pagination, small helpers."""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import streamlit as st
from PIL import Image

from config import settings
from config.settings import APP_NAME

# ---------------------------------------------------------------- look & feel
# Colours/fonts of the whole app live in .streamlit/config.toml ([theme] and [theme.sidebar]).
# This CSS only covers what the theme file cannot: spacing, cards and the font of the menu links.
_CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
h1, h2, h3 {color: #23272F; font-weight: 600; letter-spacing: -0.01em;}
[data-testid="stMetric"] {background: #F4F5F7; border: 1px solid #E3E5E9; padding: 14px 18px; border-radius: 10px;}
[data-testid="stMetricLabel"] {color: #5B6270;}
/* ---- sidebar menu text: change size / weight / colour here ---- */
[data-testid="stSidebarNavLink"] span {font-size: 0.98rem; font-weight: 500;}
[data-testid="stSidebarNavLink"][aria-current="page"] span {font-weight: 700;}
.small-note {color: #5B6270; font-size: 0.85rem;}
</style>
"""


def chrome() -> None:
    """Global elements shared by all pages. Called once from app.py (the router)."""
    st.markdown(_CSS, unsafe_allow_html=True)
    if settings.LOGO_PATH.exists():
        icon = str(settings.ICON_PATH) if settings.ICON_PATH.exists() else None
        st.logo(str(settings.LOGO_PATH), size="large", icon_image=icon)
    with st.sidebar:
        st.divider()
        st.date_input("Tanggal proses", value=dt.date.today(), key="run_date", format="DD/MM/YYYY",
                      help="Dipakai untuk memeriksa tanggal mendatang dan 'bukan bulan berjalan'.")


@st.cache_data(show_spinner=False)
def _banner_bytes(path: str, mtime: float, height: int) -> bytes:
    """Centre-crop the photo to a wide strip so any picture fits the header nicely."""
    img = Image.open(path).convert("RGB")
    target_ratio = 1400 / height
    w, h = img.size
    if w / h > target_ratio:                       # too wide -> crop sides
        nw = int(h * target_ratio)
        img = img.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    else:                                          # too tall -> crop top/bottom
        nh = int(w / target_ratio)
        img = img.crop((0, (h - nh) // 2, w, (h + nh) // 2))
    img = img.resize((1400, height))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def page_header(title: str, subtitle: str = "") -> None:
    p = settings.BANNER_PATH
    if p.exists():
        st.image(_banner_bytes(str(p), p.stat().st_mtime, settings.BANNER_HEIGHT), width="stretch")
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
