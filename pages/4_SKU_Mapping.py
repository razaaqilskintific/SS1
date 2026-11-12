import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from config.distributors import VALID_SCOPES
from processors.mapping_processor import APPROVED, suggest_for_unmapped
from services.mapping_service import mapping_to_xlsx, read_mapping_file
from ui import components as ui, state

ui.page_setup("SKU Mapping", "🔗")
state.init()
ui.page_header("SKU Mapping", "Kode asli distributor → SKU Fix. Mapping dibaca otomatis dari Google Sheets "
                              "(bila diatur) ditambah aturan yang disimpan di aplikasi.")
store = state.get_store()
mapping, info, local = state.effective_mapping()
res = st.session_state.get("result")


def changed(msg: str) -> None:
    state.reapply_mapping()
    state.audit(msg)
    st.toast(msg)
    st.rerun()


# ------------------------------------------------------------ source status
c = st.columns(4)
c[0].metric("Aturan aktif", ui.fmt_int(len(mapping[mapping["status"] == APPROVED]) if len(mapping) else 0))
c[1].metric("Sumber", info["source"])
c[2].metric("Aturan dari Google Sheets", ui.fmt_int(info["remote_rows"]))
c[3].metric("Aturan tambahan lokal", ui.fmt_int(len(local)))
if info["error"]:
    st.error(info["error"])
for p in info["problems"]:
    (st.info if p.startswith("Info:") else st.warning)(f"Google Sheets: {p}")

with st.expander("Sumber mapping: Google Sheets (otomatis) atau lokal", expanded=not info["url"]):
    st.markdown(
        "**Disarankan:** simpan mapping di Google Sheet yang tetap kamu rawat. Aplikasi mengambilnya otomatis (di-cache 5 menit). "
        "Kolom minimal: `Kode DST` (atau `Kode Asli`) dan `Kode HO` (atau `SKU Fix`). Baris judul di atas header tidak masalah. "
        "Bagikan sheet sebagai **Siapa saja yang memiliki link → Pelihat**.")
    url_in = st.text_input("Link Google Sheet mapping", value=info["url"], placeholder="https://docs.google.com/spreadsheets/d/…")
    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("Pakai link ini", disabled=not url_in.strip()):
        st.session_state.mapping_url_override = url_in.strip()
        st.session_state.remote_nonce += 1
        changed("Sumber mapping diganti ke Google Sheets (sesi ini)")
    if b2.button("Muat ulang sekarang", disabled=not info["url"]):
        st.session_state.remote_nonce += 1
        changed("Mapping dimuat ulang dari Google Sheets")
    st.caption("Agar link tersimpan permanen, isi `MAPPING_SHEET_URL` di Streamlit Secrets (lihat README).")

tab_un, tab_tbl, tab_up = st.tabs(["Belum ter-mapping", "Tabel mapping", "Upload & backup"])

# ------------------------------------------------------------ unmapped
with tab_un:
    if res is None:
        st.info("Proses file dulu di menu Upload Files agar daftar SKU yang belum ter-mapping muncul.")
    else:
        un = state.unmapped_table(res)
        if un.empty:
            st.success("Semua SKU sudah ter-mapping.")
        else:
            st.markdown(f"**{len(un)} kode** belum ada di mapping. Saran hanya usulan dan baru dipakai setelah kamu centang **Simpan**.")
            sug = suggest_for_unmapped(un.rename(columns={"sku_raw": "sku_raw"})[["distributor", "sku_raw"]], mapping)
            m = un.merge(sug.rename(columns={"original_sku": "sku_raw"}), on=["distributor", "sku_raw"], how="left")
            view = pd.DataFrame({
                "Simpan": m["rule"].eq("buang awalan G").fillna(False).values,
                "Distributor": m["distributor"].values, "Kode asli": m["sku_raw"].values,
                "Baris": m["baris"].values, "Jenis": m["jenis"].values,
                "SKU Fix": m["suggested_sku_fix"].fillna("").values, "Dasar saran": m["rule"].fillna("").values})
            edited = st.data_editor(view, hide_index=True, width="stretch", key="unmapped_editor",
                                    disabled=["Distributor", "Kode asli", "Baris", "Jenis", "Dasar saran"],
                                    column_config={"Simpan": st.column_config.CheckboxColumn(width="small"),
                                                   "SKU Fix": st.column_config.TextColumn(help="Isi atau koreksi SKU Fix yang benar")})
            s1, s2, _ = st.columns([1, 1, 3])
            if s1.button("Simpan yang dicentang", type="primary"):
                pick = edited[edited["Simpan"] & (edited["SKU Fix"].str.strip() != "")]
                if pick.empty:
                    st.warning("Belum ada baris dicentang yang SKU Fix-nya terisi.")
                else:
                    nun = pick.groupby("Kode asli")["SKU Fix"].nunique()
                    if (nun > 1).any():
                        st.error(f"Kode yang sama diberi SKU Fix berbeda: {', '.join(nun[nun > 1].index)}")
                    else:
                        rows = pick.drop_duplicates("Kode asli")
                        store.upsert(pd.DataFrame({
                            "scope": "*", "original_sku": rows["Kode asli"].values, "sku_fix": rows["SKU Fix"].str.strip().values,
                            "status": APPROVED, "note": "Ditambahkan dari aplikasi"}), note="dari daftar belum ter-mapping")
                        changed(f"{len(rows)} aturan mapping disimpan")
            s2.download_button("Unduh daftar (CSV)", un.rename(columns={"sku_raw": "Kode asli"}).to_csv(index=False).encode("utf-8"),
                               file_name="SKU belum ter-mapping.csv", mime="text/csv",
                               help="Lengkapi di Google Sheet mapping, lalu klik 'Muat ulang sekarang'.")

# ------------------------------------------------------------ table
with tab_tbl:
    q = st.text_input("Cari kode asli / SKU Fix / nama")
    t = mapping.copy()
    local_keys = set(zip(local["scope"], local["original_sku"])) if len(local) else set()
    t.insert(0, "Sumber", ["Lokal (app)" if (s, k) in local_keys else "Google Sheets" if info["url"] else "Lokal (app)"
                           for s, k in zip(t["scope"], t["original_sku"])])
    if q:
        s = q.strip().lower()
        t = t[t["original_sku"].str.lower().str.contains(s, regex=False) | t["sku_fix"].str.lower().str.contains(s, regex=False)
              | t["note"].str.lower().str.contains(s, regex=False)]
    ui.paged(t.rename(columns={"scope": "Scope", "original_sku": "Kode asli", "sku_fix": "SKU Fix", "status": "Status",
                               "note": "Catatan"})[["Sumber", "Scope", "Kode asli", "SKU Fix", "Status", "Catatan"]], "maptbl")
    st.markdown("**Tambah / ubah satu aturan**")
    with st.form("one_rule", clear_on_submit=True):
        f = st.columns([1, 2, 2, 1])
        scope = f[0].selectbox("Berlaku untuk", VALID_SCOPES, help="'*' = semua distributor")
        orig = f[1].text_input("Kode asli")
        fix = f[2].text_input("SKU Fix")
        status = f[3].selectbox("Status", ["approved", "rejected"], help="'rejected' menonaktifkan aturan dari Google Sheets")
        if st.form_submit_button("Simpan aturan"):
            if not orig.strip() or (status == "approved" and not fix.strip()):
                st.error("Kode asli dan SKU Fix wajib diisi.")
            else:
                store.upsert(pd.DataFrame([{"scope": scope, "original_sku": orig, "sku_fix": fix, "status": status,
                                            "note": "Diisi manual di aplikasi"}]), note="manual")
                changed(f"Aturan {orig.strip().upper()} disimpan")
    if len(local):
        st.markdown("**Aturan tambahan lokal**")
        pick = st.selectbox("Hapus aturan lokal", [""] + [f"{s} | {k}" for s, k in zip(local["scope"], local["original_sku"])])
        if pick and st.button("Hapus aturan terpilih"):
            sc, kk = [x.strip() for x in pick.split("|", 1)]
            store.delete(sc, kk)
            changed(f"Aturan {kk} dihapus")

# ------------------------------------------------------------ upload & backup
with tab_up:
    st.markdown("**Unggah file mapping** (.xlsx atau .csv). Format file lama (Kode DST / Nama DST / Kode HO) bisa langsung dipakai.")
    f = st.file_uploader("File mapping", type=["xlsx", "csv"], key="map_upload")
    if f is not None:
        df_up, problems = read_mapping_file(f.name, f.getvalue())
        for p in problems:
            (st.info if p.startswith("Info:") else st.warning)(p)
        st.caption(f"{len(df_up):,} aturan valid terbaca.")
        st.dataframe(df_up.head(50), width="stretch", hide_index=True)
        has_conflict = any(p.startswith("Konflik") for p in problems)
        u1, u2, _ = st.columns([1, 1, 3])
        if u1.button("Gabungkan ke mapping lokal", type="primary", disabled=df_up.empty or has_conflict):
            store.upsert(df_up, note=f"upload {f.name}")
            changed(f"{len(df_up)} aturan digabung dari {f.name}")
        if u2.button("Ganti seluruh mapping lokal", disabled=df_up.empty or has_conflict,
                     help="Mapping lokal lama disimpan dulu sebagai snapshot."):
            store.replace_all(df_up, note=f"upload {f.name}")
            changed(f"Mapping lokal diganti dengan {len(df_up)} aturan")
        if has_conflict:
            st.error("Perbaiki konflik di file dulu (kode yang sama tidak boleh punya SKU Fix berbeda).")
    st.divider()
    st.download_button("Export mapping aktif (.xlsx)", mapping_to_xlsx(mapping), file_name="SKU Mapping.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    v = store.version()
    st.caption(f"Versi mapping lokal: {v['version']} · diubah {v['updated_at'] or '-'}")
    snaps = store.snapshots()
    if len(snaps):
        st.dataframe(snaps, width="stretch", hide_index=True)
        sid = st.selectbox("Kembalikan ke snapshot #", [None] + list(snaps["id"]))
        if sid and st.button("Kembalikan"):
            store.restore(int(sid))
            changed(f"Mapping lokal dikembalikan ke snapshot #{sid}")
