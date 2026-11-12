import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import streamlit as st

from config import settings
from services.compilation_service import compute_stats
from services.export_service import (BlockedByCriticalErrors, combined_workbook, sales_workbook, stock_workbook)
from ui import components as ui, state

ui.page_setup("Download Center", "⬇️")
state.init()
ui.page_header("Download Center", "File hasil berisi kolom standar saja. Tidak ada metadata internal.")
res = state.require_result()
stats = compute_stats(res)
unm = state.unmapped_table(res)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

k = st.columns(3)
k[0].metric("Baris Sales", ui.fmt_int(len(res.sales)))
k[1].metric("Baris Stock", ui.fmt_int(len(res.stock)))
k[2].metric("SKU belum ter-mapping", ui.fmt_int(len(unm)))
if len(unm):
    if settings.UNMAPPED_POLICY == "block":
        st.error("Kebijakan saat ini memblokir unduhan selama masih ada SKU yang belum ter-mapping.")
    else:
        st.warning(f"{len(unm)} kode SKU belum ter-mapping dan dipakai **apa adanya** di kolom SKU Fix. "
                   "Lengkapi di menu SKU Mapping sebelum file dipakai.")
n_off = int(res.issues["code"].eq("NOT_CURRENT_MONTH").sum())
if n_off:
    st.warning(f"{n_off} sheet bukan bulan berjalan (tetap diproses). Lihat Validation Report.")

excl = st.session_state.exclude_invalid
try:
    sales_bytes = sales_workbook(res, excl)
    stock_bytes = stock_workbook(res, excl)
    both_bytes = combined_workbook(res, excl)
except BlockedByCriticalErrors as e:
    st.error(f"Unduhan diblokir: {e} Buka **Validation Report**.")
    st.stop()

if excl:
    st.info("Baris error kritis dikeluarkan dari file (tercatat di jejak audit).")
c = st.columns(3)
c[0].download_button("Sales Summary.xlsx", sales_bytes, file_name="Sales Summary.xlsx", mime=XLSX, type="primary", width="stretch")
c[1].download_button("Stock Summary.xlsx", stock_bytes, file_name="Stock Summary.xlsx", mime=XLSX, type="primary", width="stretch")
c[2].download_button("Combined Report.xlsx", both_bytes, file_name="Combined Report.xlsx", mime=XLSX, width="stretch",
                     help="Sheet 1: Sales Summary, Sheet 2: Stock Summary")
st.caption("Combined Report berisi dua sheet: Sales Summary dan Stock Summary.")
