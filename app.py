"""Dashboard (entry point). Run with:  streamlit run app.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from config.distributors import DISTRIBUTOR_ORDER
from processors.validation import CRITICAL
from services.compilation_service import compute_stats
from ui import components as ui, state

ui.page_setup("Dashboard", "📊")
state.init()
ui.page_header("Daily Sales & Stock Compiler",
               "Konsolidasi harian Sales dan Stock distributor Sumatera menjadi dua file standar.")

res = st.session_state.get("result")
mapping, minfo, _ = state.effective_mapping()

if res is None:
    st.info("**Mulai di sini:** buka menu **Upload Files** di sebelah kiri → unggah semua file distributor hari ini "
            "→ klik **Proses**. Hasilnya muncul di halaman Sales, Stock, Validation, lalu unduh di **Download Center**.")
    c = st.columns(3)
    c[0].metric("Aturan mapping aktif", ui.fmt_int(len(mapping)))
    c[1].metric("Sumber mapping", minfo["source"])
    c[2].metric("Tanggal proses", f"{state.run_date():%d/%m/%Y}")
    if minfo["error"]:
        st.error(minfo["error"])
    st.stop()

stats = compute_stats(res)
unm = state.unmapped_table(res)

r1 = st.columns(3)
r1[0].metric("Total file diunggah", ui.fmt_int(stats["files_uploaded"]))
r1[1].metric("Total record Sales", ui.fmt_int(stats["sales_records"]))
r1[2].metric("Total record Stock", ui.fmt_int(stats["stock_records"]))
r2 = st.columns(3)
r2[0].metric("Sheet berhasil diproses", ui.fmt_int(len(res.source_rows)))
r2[1].metric("File/sheet gagal", ui.fmt_int(stats["failed_files"]))
r2[2].metric("SKU belum ter-mapping", ui.fmt_int(len(unm)), help="Jumlah kode unik. Jumlah barisnya: "
             + ui.fmt_int(stats["unmapped_sku_rows"]))

st.subheader("Status pemrosesan")
t = st.session_state.compiled_at
st.caption(f"Kompilasi terakhir: {t:%d/%m/%Y %H:%M:%S} · Tanggal proses {res.run_date:%d/%m/%Y} · "
           f"Mapping: {minfo['source']} ({ui.fmt_int(len(mapping))} aturan)")
issues = res.issues
if stats["critical"]:
    st.error(f"{stats['critical']} error kritis. Perbaiki atau keluarkan barisnya di **Validation Report** sebelum mengunduh.")
for msg in issues[issues["code"] == "NOT_CURRENT_MONTH"].itertuples():
    st.warning(f"{msg.file}: {msg.message}")
if len(unm):
    st.warning(f"{len(unm)} kode SKU belum ada di mapping. Lengkapi di menu **SKU Mapping** (tab *Belum Ter-mapping*).")
if minfo["error"]:
    st.error(minfo["error"])
if not stats["critical"] and not len(unm):
    st.success("Tidak ada error kritis dan semua SKU sudah ter-mapping.")

st.subheader("Ringkasan per distributor")
c1, c2 = st.columns(2)
for col, title, df, unit in ((c1, "Sales", res.sales, "QTY terjual"), (c2, "Stock", res.stock, "QTY stok")):
    if len(df):
        g = df.groupby("distributor").agg(Baris=("qty", "size"), **{unit: ("qty", "sum")})
        g = g.reindex([d for d in DISTRIBUTOR_ORDER if d in g.index])
        col.markdown(f"**{title}**")
        col.dataframe(g, width="stretch")
