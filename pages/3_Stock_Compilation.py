import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st

from config.distributors import BRANCH_ORDER, DISTRIBUTOR_ORDER
from config.settings import STOCK_OUTPUT_COLUMNS
from ui import components as ui, state

ui.page_setup("Stock Compilation", "📦")
state.init()
ui.page_header("Stock Compilation", "Pratinjau Stock Summary. Filter di sini hanya memengaruhi tampilan, bukan file unduhan.")
res = state.require_result()
df = state.stock_frame(res)
if df.empty:
    st.warning("Tidak ada data Stock pada kompilasi ini.")
    st.stop()

c = st.columns(4)
dist = c[0].multiselect("Distributor", [d for d in DISTRIBUTOR_ORDER if d in set(df["Distributor"])])
branch = c[1].multiselect("Branch", [b for b in BRANCH_ORDER if b in set(df["BRANCH"])])
sku = c[2].text_input("SKU (SKU_Fix atau SKU asli)")
hide_zero = c[3].checkbox("Sembunyikan stok 0")
c2 = st.columns([1, 1, 4])
only_unmapped = c2[0].checkbox("Hanya SKU belum ter-mapping")
details = c2[1].checkbox("Tampilkan detail sumber")

m = df
if dist:
    m = m[m["Distributor"].isin(dist)]
if branch:
    m = m[m["BRANCH"].isin(branch)]
if sku:
    s = sku.strip().lower()
    m = m[m["SKU_Fix"].str.lower().str.contains(s, regex=False) | m["SKU asli"].str.lower().str.contains(s, regex=False)]
if hide_zero:
    m = m[m["QTY"] != 0]
if only_unmapped:
    m = m[m["Status mapping"] == "UNMAPPED"]

k = st.columns(3)
k[0].metric("Baris ditampilkan", ui.fmt_int(len(m)), f"dari {ui.fmt_int(len(df))}", delta_color="off")
k[1].metric("Total QTY stok", ui.fmt_int(m["QTY"].sum()))
k[2].metric("Baris SKU belum ter-mapping", ui.fmt_int((m["Status mapping"] == "UNMAPPED").sum()))
periods = df.groupby("Distributor")["Periode stok"].agg(lambda s: s.dropna().max())
if periods.notna().any():
    st.caption("Periode stok per distributor: " + " · ".join(f"{d}: {p:%d/%m/%Y}" for d, p in periods.items() if p == p and p is not None))

cols = STOCK_OUTPUT_COLUMNS + (["Distributor", "SKU asli", "Status mapping", "Periode stok", "File sumber", "Sheet", "Baris sumber", "Valid"] if details else [])
ui.paged(m[cols], "stock", {"Periode stok": st.column_config.DateColumn(format="DD/MM/YYYY")})
