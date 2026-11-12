"""Orchestration: detect -> extract -> (re-runnable) mapping -> validation summary.

Extraction results are kept in `CompilationResult` so that editing the mapping only re-runs
`apply_mapping`, never the file upload/extraction.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import settings
from config.distributors import BRANCH_ORDER, DISTRIBUTOR_ORDER
from processors import file_detector as fd
from processors.mapping_processor import (UNMAPPED, apply_mapping_to_records, build_lookup)
from processors.sales_processor import RECORD_COLUMNS as SALES_COLS, extract_sales
from processors.stock_processor import RECORD_COLUMNS as STOCK_COLS, extract_stock
from processors.validation import (CRITICAL, INFO, INVALID_QTY_CODES, ISSUE_COLUMNS, MISSING_CODES, WARNING,
                                   IssueLog, find_duplicate_transactions, month_of)
from utils.duplicate_detector import data_fingerprint, key_set, overlap_ratio
from utils.excel_reader import Book, UnsupportedFileError


@dataclass
class FileInput:
    name: str
    data: bytes


@dataclass
class CompilationResult:
    run_date: dt.date
    detections: pd.DataFrame
    sales: pd.DataFrame
    stock: pd.DataFrame
    base_issues: pd.DataFrame
    mapping_issues: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ISSUE_COLUMNS))
    source_rows: Dict[str, int] = field(default_factory=dict)
    failed_files: List[dict] = field(default_factory=list)
    mapping_conflicts: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def issues(self) -> pd.DataFrame:
        return pd.concat([self.base_issues, self.mapping_issues], ignore_index=True)


# ------------------------------------------------------------------ detection
def open_books(files: List[FileInput], log: Optional[IssueLog] = None) -> Tuple[Dict[str, Book], List[dict]]:
    books, failed = {}, []
    for f in files:
        try:
            books[f.name] = Book(f.name, f.data)
        except Exception as e:  # unreadable / not Excel
            failed.append({"file": f.name, "error": str(e)})
            if log is not None:
                log.add(CRITICAL, "FAILED_FILE", f"File tidak dapat dibaca: {e}", file=f.name)
    return books, failed


def detect_books(books: Dict[str, Book], overrides: Optional[dict] = None) -> List[fd.Detection]:
    """Detect every sheet. `overrides[(file, sheet)] = (distributor, 'Sales'|'Stock')` = manual correction."""
    overrides = overrides or {}
    dets: List[fd.Detection] = []
    seen_hash: Dict[str, str] = {}
    for name, book in books.items():
        dup_of = seen_hash.get(book.sha256)
        if dup_of:
            dets.append(fd.Detection(name, "*", status=f"Ignored: file identik dengan {dup_of}"))
            continue
        seen_hash[book.sha256] = name
        for sh in book.sheet_names:
            df = book.sheet(sh)
            det = fd.detect_sheet(name, sh, df)
            if (name, sh) in overrides:
                det = fd.apply_override(det, df, *overrides[(name, sh)])
            dets.append(det)
    return dets


def detections_frame(dets: List[fd.Detection]) -> pd.DataFrame:
    cols = ["file_name", "sheet_name", "distributor", "data_type", "confidence", "status", "score", "notes"]
    return pd.DataFrame([d.as_dict() for d in dets], columns=list(fd.Detection.__dataclass_fields__)).reindex(columns=cols)


# ------------------------------------------------------------------ compilation
def compile_files(files: List[FileInput], run_date: Optional[dt.date] = None, overrides: Optional[dict] = None,
                  process_review: bool = False, exclude: Optional[set] = None) -> CompilationResult:
    run_date = run_date or dt.date.today()
    exclude = exclude or set()
    log = IssueLog()
    books, failed = open_books(files, log)
    dets = detect_books(books, overrides)
    for d in dets:
        if d.status.startswith("Ignored: file identik"):
            log.add(WARNING, "DUPLICATE_FILE", f"{d.file_name}: {d.status[9:]}; file dilewati", file=d.file_name)
        if d.status == "Needs confirmation" and not process_review:
            log.add(WARNING, "NEEDS_CONFIRMATION", f"Sheet belum dikonfirmasi: {d.notes}",
                    file=d.file_name, sheet=d.sheet_name, distributor=d.distributor)

    sales_parts, stock_parts = [], []
    source_rows: Dict[str, int] = {}
    seen_fp: Dict[Tuple[str, str], str] = {}
    seen_keys: Dict[str, Tuple[set, str]] = {}
    for det in dets:
        ok = det.processable and (det.status == "Detected" or process_review)
        if not ok or (det.file_name, det.sheet_name) in exclude:
            continue
        label = f"{det.file_name}|{det.sheet_name}"
        try:
            df = books[det.file_name].sheet(det.sheet_name)
            ctx = dict(file=det.file_name, sheet=det.sheet_name, distributor=det.distributor)
            if not det.distributor:
                raise ValueError("Distributor belum ditentukan")
            if det.data_type == "Sales":
                rec, n = extract_sales(df, det.profile, det.distributor, det.file_name, det.sheet_name,
                                       det.header_row, run_date, log)
                fp_cols = ["dst_branch", "sales_id", "cust_id", "invoice_date", "invoice_no", "sku_raw", "qty"]
                key_cols = ["distributor", "invoice_no", "cust_id", "sku_raw", "qty"]
            else:
                rec, n = extract_stock(df, det.profile, det.distributor, det.file_name, det.sheet_name,
                                       det.header_row, run_date, log)
                fp_cols = ["branch", "sku_raw", "qty"]
                key_cols = ["branch", "sku_raw"]
            source_rows[label] = n
            if rec.empty:
                log.add(WARNING, "NO_DATA_ROWS", "Sheet dikenali tetapi tidak berisi baris data", **ctx)
                continue

            # --- duplicate source detection (identical data is skipped; partial overlap only warns)
            fp = data_fingerprint(rec, fp_cols)
            prev = seen_fp.get((det.data_type, fp))
            if prev:
                log.add(WARNING, "DUPLICATE_SOURCE", f"Data identik dengan {prev}; sheet ini dilewati agar tidak terhitung dua kali", **ctx)
                continue
            seen_fp[(det.data_type, fp)] = label
            keys = key_set(rec, key_cols)
            for other_label, (other_keys, other_file) in seen_keys.items():
                if other_file != det.file_name and len(keys) >= 5 and overlap_ratio(keys, other_keys) >= 0.9:
                    log.add(WARNING, "OVERLAPPING_SOURCE",
                            f"≥90% baris sama dengan {other_label}; kemungkinan data yang sama di dua file (tetap diproses)", **ctx)
            seen_keys[label] = (keys, det.file_name)

            # --- "not the running month" notification (processed anyway)
            if det.data_type == "Sales":
                dates = rec["invoice_date"].dropna()
                off = dates[[(d.year, d.month) != (run_date.year, run_date.month) for d in dates]]
                if len(off):
                    log.add(WARNING, "NOT_CURRENT_MONTH",
                            f"{len(off)} baris bertanggal bukan bulan berjalan ({month_of(run_date)}): "
                            f"{off.min():%d/%m/%Y}–{off.max():%d/%m/%Y}", **ctx)
                sales_parts.append(rec)
            else:
                per = rec["stock_period"].dropna().unique()
                if len(per) and (per[0].year, per[0].month) != (run_date.year, run_date.month):
                    log.add(WARNING, "NOT_CURRENT_MONTH",
                            f"Periode stok {per[0]:%d/%m/%Y} bukan bulan berjalan ({month_of(run_date)}); tetap diproses", **ctx)
                if not len(per) and det.profile in ("BMS_STOCK", "BLT_STOCK"):
                    log.add(INFO, "NO_STOCK_PERIOD", "Tanggal stok tidak ditemukan di header file", **ctx)
                stock_parts.append(rec)
        except Exception as e:
            failed.append({"file": det.file_name, "sheet": det.sheet_name, "error": str(e)})
            log.add(CRITICAL, "FAILED_SHEET", f"Gagal memproses sheet: {e}", file=det.file_name,
                    sheet=det.sheet_name, distributor=det.distributor)

    sales = _concat(sales_parts, SALES_COLS)
    stock = _concat(stock_parts, STOCK_COLS)
    sales = _order(sales, "distributor", DISTRIBUTOR_ORDER, ["dst_branch"], BRANCH_ORDER)
    stock = _order(stock, "distributor", DISTRIBUTOR_ORDER, ["branch"], BRANCH_ORDER)

    dup = find_duplicate_transactions(sales)
    for _, r in dup.iterrows():
        log.add(WARNING, "DUPLICATE_TRANSACTION", "Baris dengan kunci transaksi identik (tidak dihapus, mohon cek)",
                file=r.source_file, sheet=r.source_sheet, row=int(r.source_row), distributor=r.distributor,
                original={"invoice": r.invoice_no, "sku": r.sku_raw, "qty": r.qty})
    if not stock.empty:
        for _, r in stock[stock.duplicated(["branch", "sku_raw"], keep=False)].iterrows():
            log.add(WARNING, "DUPLICATE_STOCK_KEY", "Kombinasi cabang+SKU muncul lebih dari sekali",
                    file=r.source_file, sheet=r.source_sheet, row=int(r.source_row), distributor=r.distributor,
                    original={"branch": r.branch, "sku": r.sku_raw, "qty": r.qty})

    res = CompilationResult(run_date=run_date, detections=detections_frame(dets), sales=sales, stock=stock,
                            base_issues=log.to_df(), source_rows=source_rows, failed_files=failed)
    return apply_mapping(res, pd.DataFrame(columns=["scope", "original_sku", "sku_fix", "status", "note", "updated_at"]))


def _concat(parts: List[pd.DataFrame], cols: List[str]) -> pd.DataFrame:
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def _order(df: pd.DataFrame, c1: str, o1: List[str], c2: List[str], o2: List[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["_seq"] = range(len(out))
    out["_r1"] = out[c1].map(lambda v: o1.index(v) if v in o1 else 99)
    out["_r2"] = out[c2[0]].map(lambda v: o2.index(v) if v in o2 else 99)
    return out.sort_values(["_r1", "_r2", "_seq"], kind="stable").drop(columns=["_seq", "_r1", "_r2"]).reset_index(drop=True)


# ------------------------------------------------------------------ mapping (re-runnable)
def apply_mapping(res: CompilationResult, mapping: pd.DataFrame, policy: Optional[str] = None) -> CompilationResult:
    policy = policy or settings.UNMAPPED_POLICY
    passthrough = policy == "passthrough_flagged"
    res.sales = apply_mapping_to_records(res.sales, mapping, passthrough)
    res.stock = apply_mapping_to_records(res.stock, mapping, passthrough)
    _, _, res.mapping_conflicts = build_lookup(mapping)
    log = IssueLog()
    sev = WARNING if passthrough else CRITICAL
    for kind, df in (("Sales", res.sales), ("Stock", res.stock)):
        if df.empty:
            continue
        miss = df[df["mapping_status"] == UNMAPPED]
        for (dist, f, sh, sku), g in miss.groupby(["distributor", "source_file", "source_sheet", "sku_raw"], sort=False):
            log.add(sev, "UNMAPPED_SKU", f"[{kind}] SKU belum ada di mapping ({len(g)} baris)"
                    + (" — dipakai apa adanya di kolom SKU Fix" if passthrough else ""),
                    file=f, sheet=sh, row=int(g["source_row"].iloc[0]), distributor=dist, original={"sku": sku},
                    suggestion="Tambahkan di file/tab SKU Mapping lalu proses ulang")
    for _, c in res.mapping_conflicts.iterrows():
        log.add(CRITICAL, "MAPPING_CONFLICT", f"Mapping bentrok untuk {c.scope}/{c.original_sku}: {c.sku_fix_a} vs {c.sku_fix_b}")
    res.mapping_issues = log.to_df()
    return res


# ------------------------------------------------------------------ report
def compute_stats(res: CompilationResult) -> dict:
    iss = res.issues
    codes = iss["code"] if not iss.empty else pd.Series(dtype=object)
    return {
        "files_uploaded": res.detections["file_name"].nunique() if not res.detections.empty else 0,
        "total_source_rows": int(sum(res.source_rows.values())),
        "sales_records": len(res.sales), "stock_records": len(res.stock),
        "processed_ok": int(res.sales["is_valid"].sum() + res.stock["is_valid"].sum()) if len(res.sales) + len(res.stock) else 0,
        "unmapped_sku_rows": int(((res.sales.get("mapping_status") == UNMAPPED).sum() if len(res.sales) else 0)
                                 + ((res.stock.get("mapping_status") == UNMAPPED).sum() if len(res.stock) else 0)),
        "invalid_quantity": int(codes.isin(INVALID_QTY_CODES).sum()),
        "missing_required": int(codes.isin(MISSING_CODES).sum()),
        "duplicate_warnings": int(codes.isin({"DUPLICATE_TRANSACTION", "DUPLICATE_STOCK_KEY", "DUPLICATE_SOURCE",
                                              "DUPLICATE_FILE", "OVERLAPPING_SOURCE"}).sum()),
        "failed_files": len({(f["file"], f.get("sheet", "")) for f in res.failed_files}),
        "critical": int((iss["severity"] == CRITICAL).sum()) if not iss.empty else 0,
        "warnings": int((iss["severity"] == WARNING).sum()) if not iss.empty else 0,
        "info": int((iss["severity"] == INFO).sum()) if not iss.empty else 0,
    }
