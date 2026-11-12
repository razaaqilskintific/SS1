import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from services.compilation_service import compute_stats
from ui import components as ui, state

ui.page_setup("Validation Report", "✅")
state.init()
ui.page_header("Validation Report", "Semua temuan disertai file, sheet, nomor baris Excel asli, dan saran perbaikan. Data sumber tidak pernah diubah.")
res = state.require_result()
stats = compute_stats(res)

k = st.columns(4)
k[0].metric("Total baris sumber", ui.fmt_int(stats["total_source_rows"]))
k[1].metric("Berhasil diproses", ui.fmt_int(stats["processed_ok"]))
k[2].metric("SKU belum ter-mapping (baris)", ui.fmt_int(stats["unmapped_sku_rows"]))
k[3].metric("File/sheet gagal", ui.fmt_int(stats["failed_files"]))
k = st.columns(4)
k[0].metric("Qty tidak valid", ui.fmt_int(stats["invalid_quantity"]))
k[1].metric("Field wajib kosong", ui.fmt_int(stats["missing_required"]))
k[2].metric("Peringatan duplikat", ui.fmt_int(stats["duplicate_warnings"]))
k[3].metric("Kritis / Peringatan / Info", f"{stats['critical']} / {stats['warnings']} / {stats['info']}")

# ---- critical rows policy
bad = int((~res.sales["is_valid"]).sum() + (~res.stock["is_valid"]).sum()) if len(res.sales) + len(res.stock) else 0
if bad:
    st.error(f"{bad} baris memiliki error kritis dan memblokir unduhan.")
    def _toggle():
        state.audit("Baris error kritis " + ("DIKELUARKAN dari output" if st.session_state.exclude_invalid else "diikutkan kembali (unduhan diblokir)"))
    st.checkbox("Keluarkan baris error kritis dari output (dicatat di jejak audit)", key="exclude_invalid", on_change=_toggle)
else:
    st.success("Tidak ada baris error kritis.")

# ---- filters
iss = res.issues
if iss.empty:
    st.info("Tidak ada temuan validasi.")
    st.stop()
c = st.columns(4)
sev = c[0].multiselect("Severity", ["Critical", "Warning", "Info"], default=["Critical", "Warning"])
dist = c[1].multiselect("Distributor", sorted(x for x in iss["distributor"].unique() if x))
files = c[2].multiselect("File", sorted(x for x in iss["file"].unique() if x))
codes = c[3].multiselect("Jenis temuan", sorted(iss["code"].unique()))
m = iss
if sev:
    m = m[m["severity"].isin(sev)]
if dist:
    m = m[m["distributor"].isin(dist)]
if files:
    m = m[m["file"].isin(files)]
if codes:
    m = m[m["code"].isin(codes)]
order = {"Critical": 0, "Warning": 1, "Info": 2}
m = m.sort_values(["severity", "code"], key=lambda s: s.map(order) if s.name == "severity" else s, kind="stable")

summary = m.groupby(["severity", "code"]).size().rename("Jumlah").reset_index()
st.dataframe(summary, width="stretch", hide_index=True)
ui.paged(m.rename(columns={"severity": "Severity", "code": "Jenis", "distributor": "Distributor", "file": "File", "sheet": "Sheet",
                           "row": "Baris", "message": "Keterangan", "original": "Nilai asli", "suggestion": "Saran"}), "val")
st.download_button("Unduh temuan (CSV)", m.to_csv(index=False).encode("utf-8"), file_name="Validation Report.csv", mime="text/csv")

with st.expander("Jejak audit"):
    a = pd.DataFrame(st.session_state.audit)
    st.markdown("**Kegiatan di sesi ini**")
    st.dataframe(a if len(a) else pd.DataFrame({"info": ["Belum ada"]}), width="stretch", hide_index=True)
    st.markdown("**Perubahan mapping**")
    st.dataframe(state.get_store().audit(), width="stretch", hide_index=True)
