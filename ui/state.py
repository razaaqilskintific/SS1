"""Shared session state and cached resources for all pages (no business logic here)."""
from __future__ import annotations

import datetime as dt
import os
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from config import settings
from processors.mapping_processor import UNMAPPED
from services import mapping_source as ms
from services.compilation_service import (CompilationResult, FileInput, apply_mapping, compile_files,
                                          detect_books, detections_frame, open_books)
from services.mapping_service import MappingStore, read_mapping_file


def init() -> None:
    ss = st.session_state
    ss.setdefault("files", [])
    ss.setdefault("result", None)
    ss.setdefault("compiled_at", None)
    ss.setdefault("exclude_invalid", False)
    ss.setdefault("audit", [])
    ss.setdefault("uploader_key", 0)
    ss.setdefault("remote_nonce", 0)


def audit(message: str) -> None:
    st.session_state.audit.append({"waktu": dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "kegiatan": message})


def run_date() -> dt.date:
    return st.session_state.get("run_date", dt.date.today())


# ------------------------------------------------------------------ mapping
@st.cache_resource
def get_store() -> MappingStore:
    return MappingStore(settings.DB_PATH)


def sheet_url() -> str:
    url = st.session_state.get("mapping_url_override", "") or os.environ.get("MAPPING_SHEET_URL", "")
    if not url:
        try:
            url = str(st.secrets.get("MAPPING_SHEET_URL", ""))
        except Exception:
            url = ""
    return url.strip()


@st.cache_data(ttl=300, show_spinner="Mengambil mapping dari Google Sheets…")
def _remote(url: str, nonce: int):
    return read_mapping_file("remote.csv", ms.fetch_bytes(ms.gsheet_csv_url(url)))


def effective_mapping() -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    """(mapping used for processing, info, local layer). Local rows win over Google Sheets rows."""
    local = get_store().load()
    info = {"source": "Lokal (database aplikasi)", "problems": [], "remote_rows": 0, "url": "", "error": ""}
    url = sheet_url()
    if url:
        try:
            remote, problems = _remote(url, st.session_state.get("remote_nonce", 0))
            info.update(source="Google Sheets + tambahan lokal", problems=problems, remote_rows=len(remote), url=url)
            return ms.merge_mappings(remote, local), info, local
        except Exception as e:   # fall back to the local layer, but say so
            info["error"] = f"Gagal mengambil Google Sheets: {e}"
    return local, info, local


def reapply_mapping() -> None:
    res: Optional[CompilationResult] = st.session_state.get("result")
    if res is not None:
        mp, _, _ = effective_mapping()
        apply_mapping(res, mp)


# ------------------------------------------------------------------ compile
@st.cache_data(show_spinner="Membaca dan mengenali file…")
def detect_cached(payload: tuple):
    files = [FileInput(n, d) for n, d in payload]
    books, failed = open_books(files)
    return detections_frame(detect_books(books)), failed


def run_compile(files, overrides: dict, excluded: set) -> CompilationResult:
    res = compile_files(files, run_date=run_date(), overrides=overrides, process_review=True, exclude=excluded)
    mp, _, _ = effective_mapping()
    apply_mapping(res, mp)
    st.session_state.result = res
    st.session_state.compiled_at = dt.datetime.now()
    st.session_state.exclude_invalid = False
    audit(f"Kompilasi: {len(files)} file, {len(res.sales):,} baris Sales, {len(res.stock):,} baris Stock")
    return res


def require_result() -> CompilationResult:
    res = st.session_state.get("result")
    if res is None:
        st.info("Belum ada data. Buka menu **Upload Files**, unggah file distributor, lalu klik **Proses**.")
        st.stop()
    return res


# ------------------------------------------------------------------ views
def sales_frame(res: CompilationResult) -> pd.DataFrame:
    d = res.sales
    return pd.DataFrame({
        "DST BRANCH": d.dst_branch, "SALES ID": d.sales_id, "CUST ID": d.cust_id, "CUST NAME": d.cust_name,
        "INVOICE DATE": d.invoice_date, "NO. INVOICE": d.invoice_no, "SKU Fix": d.sku_fix, "QTY": d.qty,
        "Distributor": d.distributor, "SKU asli": d.sku_raw, "Status mapping": d.mapping_status,
        "File sumber": d.source_file, "Sheet": d.source_sheet, "Baris sumber": d.source_row, "Valid": d.is_valid})


def stock_frame(res: CompilationResult) -> pd.DataFrame:
    d = res.stock
    return pd.DataFrame({
        "QTY": d.qty, "BRANCH": d.branch, "SKU_Fix": d.sku_fix,
        "Distributor": d.distributor, "SKU asli": d.sku_raw, "Status mapping": d.mapping_status,
        "Periode stok": d.stock_period, "File sumber": d.source_file, "Sheet": d.source_sheet,
        "Baris sumber": d.source_row, "Valid": d.is_valid})


def unmapped_table(res: CompilationResult) -> pd.DataFrame:
    parts = []
    for kind, df in (("Sales", res.sales), ("Stock", res.stock)):
        if len(df):
            m = df[df["mapping_status"] == UNMAPPED]
            if len(m):
                parts.append(m.assign(jenis=kind))
    if not parts:
        return pd.DataFrame(columns=["distributor", "sku_raw", "baris", "jenis"])
    allm = pd.concat(parts)
    g = allm.groupby(["distributor", "sku_raw"], sort=False).agg(
        baris=("sku_raw", "size"), jenis=("jenis", lambda s: ", ".join(sorted(set(s))))).reset_index()
    return g.sort_values("baris", ascending=False).reset_index(drop=True)
