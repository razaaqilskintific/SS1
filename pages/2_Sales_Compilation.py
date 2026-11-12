import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st

from config.distributors import BRANCH_ORDER, DISTRIBUTOR_ORDER
from config.settings import SALES_OUTPUT_COLUMNS
from ui import components as ui, state

ui.page_setup("Sales Compilation", "🧾")
state.init()
ui.page_header("Sales Compilation", "Pratinjau Sales Summary. Filter di sini hanya memengaruhi tampilan, bukan file unduhan.")
res = state.require_result()
df = state.sales_frame(res)
if df.empty:
    st.warning("Tidak ada data Sales pada kompilasi ini.")
    st.stop()

c = st.columns(4)
dist = c[0].multiselect("Distributor", [d for d in DISTRIBUTOR_ORDER if d in set(df["Distributor"])])
branch = c[1].multiselect("Branch", [b for b in BRANCH_ORDER if b in set(df["DST BRANCH"])])
dates = df["INVOICE DATE"].dropna()
rng = c[2].date_input("Tanggal invoice", value=(dates.min(), dates.max()), min_value=dates.min(),
                      max_value=dates.max(), format="DD/MM/YYYY") if len(dates) else ()
sku = c[3].text_input("SKU (SKU Fix atau SKU asli)")
c2 = st.columns([3, 1, 1, 1])
q = c2[0].text_input("Cari customer / invoice / sales")
only_unmapped = c2[1].checkbox("Hanya SKU belum ter-mapping")
only_invalid = c2[2].checkbox("Hanya baris error")
details = c2[3].checkbox("Tampilkan detail sumber")

m = df
if dist:
    m = m[m["Distributor"].isin(dist)]
if branch:
    m = m[m["DST BRANCH"].isin(branch)]
if len(rng) == 2:
    d = m["INVOICE DATE"]
    m = m[(d >= rng[0]) & (d <= rng[1]) | d.isna()]
if sku:
    s = sku.strip().lower()
    m = m[m["SKU Fix"].str.lower().str.contains(s, regex=False) | m["SKU asli"].str.lower().str.contains(s, regex=False)]
if q:
    s = q.strip().lower()
    hay = (m["CUST NAME"] + " " + m["CUST ID"] + " " + m["NO. INVOICE"] + " " + m["SALES ID"]).str.lower()
    m = m[hay.str.contains(s, regex=False)]
if only_unmapped:
    m = m[m["Status mapping"] == "UNMAPPED"]
if only_invalid:
    m = m[~m["Valid"]]

k = st.columns(4)
k[0].metric("Baris ditampilkan", ui.fmt_int(len(m)), f"dari {ui.fmt_int(len(df))}", delta_color="off")
k[1].metric("Total QTY", ui.fmt_int(m["QTY"].sum()))
k[2].metric("Invoice unik", ui.fmt_int(m["NO. INVOICE"].replace("", None).nunique()))
k[3].metric("Baris SKU belum ter-mapping", ui.fmt_int((m["Status mapping"] == "UNMAPPED").sum()))

cols = SALES_OUTPUT_COLUMNS + (["Distributor", "SKU asli", "Status mapping", "File sumber", "Sheet", "Baris sumber", "Valid"] if details else [])
ui.paged(m[cols], "sales", {"INVOICE DATE": st.column_config.DateColumn(format="DD/MM/YYYY")})
