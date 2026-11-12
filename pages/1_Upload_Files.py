import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from config.distributors import DISTRIBUTOR_ORDER
from services.compilation_service import FileInput
from ui import components as ui, state

ui.page_setup("Upload Files", "📤")
state.init()
ui.page_header("Upload Files", "Unggah semua file distributor sekaligus. Aplikasi mengenali distributor dan jenis data dari isi file, "
                               "bukan dari nama file.")

uploaded = st.file_uploader("File distributor (.xlsx / .xls)", type=["xlsx", "xls"], accept_multiple_files=True,
                            key=f"uploader_{st.session_state.uploader_key}")
files = [FileInput(f.name, f.getvalue()) for f in uploaded] if uploaded else []
if not files:
    st.info("Belum ada file. Seret beberapa file Sales dan Stock sekaligus ke kotak di atas.")
    st.stop()

dets, failed = state.detect_cached(tuple((f.name, f.data) for f in files))
for f in failed:
    st.error(f"**{f['file']}** tidak dapat dibaca: {f['error']}")

st.subheader("Hasil deteksi")
st.caption("Periksa tabel ini. Koreksi *Distributor* atau *Tipe* bila salah, dan hilangkan centang *Sertakan* untuk sheet yang tidak dipakai.")
ready = dets["status"].isin(["Detected", "Needs confirmation"])
ed = pd.DataFrame({
    "Sertakan": ready.values, "File": dets.file_name.values, "Sheet": dets.sheet_name.values,
    "Distributor": dets.distributor.values, "Tipe": dets.data_type.values,
    "Kepercayaan": dets.confidence.values, "Status": dets.status.values, "Catatan": dets.notes.values})
sig = hashlib.md5("|".join(f"{f.name}:{len(f.data)}" for f in files).encode()).hexdigest()[:10]
edited = st.data_editor(
    ed, hide_index=True, width="stretch", key=f"det_{sig}",
    disabled=["File", "Sheet", "Kepercayaan", "Status", "Catatan"],
    column_config={
        "Sertakan": st.column_config.CheckboxColumn(width="small"),
        "Distributor": st.column_config.SelectboxColumn(options=[""] + DISTRIBUTOR_ORDER, width="small"),
        "Tipe": st.column_config.SelectboxColumn(options=["", "Sales", "Stock"], width="small")})

overrides, excluded, to_process = {}, set(), 0
for i, row in edited.reset_index(drop=True).iterrows():
    key = (row["File"], row["Sheet"])
    if not row["Sertakan"]:
        excluded.add(key)
        continue
    d0, t0 = dets.iloc[i].distributor, dets.iloc[i].data_type
    if (row["Distributor"], row["Tipe"]) != (d0, t0) and row["Distributor"] and row["Tipe"]:
        overrides[key] = (row["Distributor"], row["Tipe"])
        to_process += 1
    elif ready.iloc[i]:
        to_process += 1

c = st.columns(3)
c[0].metric("Sheet siap diproses", ui.fmt_int(to_process))
c[1].metric("Perlu konfirmasi", ui.fmt_int(int((dets.status == "Needs confirmation").sum())))
c[2].metric("Diabaikan", ui.fmt_int(int(dets.status.str.startswith("Ignored").sum())))

go, reset, _ = st.columns([1, 1, 4])
if go.button("Proses", type="primary", disabled=to_process == 0, width="stretch"):
    with st.spinner("Memproses file…"):
        res = state.run_compile(files, overrides, excluded)
    st.success(f"Selesai: {len(res.sales):,} baris Sales dan {len(res.stock):,} baris Stock. "
               "Lanjut ke menu **Validation Report** atau **Download Center**.")
    n_crit = int((res.issues["severity"] == "Critical").sum())
    if n_crit:
        st.error(f"{n_crit} error kritis ditemukan. Lihat Validation Report.")
if reset.button("Bersihkan", width="stretch"):
    st.session_state.uploader_key += 1
    st.session_state.result = None
    st.rerun()
