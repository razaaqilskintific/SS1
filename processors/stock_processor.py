"""Stock extraction. One independent code path per layout, driven by config/stock_mapping.py."""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, List, Optional, Tuple

import pandas as pd

from config.distributors import BRANCH_ORDER, SJP_GUDANG_BRANCH, SJP_STOCK_SHEET_BRANCH
from config.stock_mapping import STOCK_PROFILES
from processors.sales_processor import check_layout
from processors.validation import CRITICAL, INFO, WARNING, IssueLog
from utils.normalization import clean_text, is_blank, parse_stock_qty, text_id, to_date

RECORD_COLUMNS = ["distributor", "branch", "sku_raw", "qty", "stock_period",
                  "source_file", "source_sheet", "source_row", "is_valid"]


def _get(row: tuple, col: int) -> Any:
    return row[col] if col < len(row) else None


def find_stock_period(df: pd.DataFrame, profile_key: str) -> Optional[dt.date]:
    """Stock date printed in the report header (BMS 'Period', BLT 'STOCK UPDATE'). None if not present."""
    labels = {"BMS_STOCK": "period", "BLT_STOCK": "stockupdate:"}
    label = labels.get(profile_key)
    if not label:
        return None
    for r in range(min(len(df), 30)):
        row = df.iloc[r].tolist()
        for c, v in enumerate(row):
            if re.sub(r"\s+", "", str(v)).lower() == label:
                for w in row[c + 1:]:
                    if not is_blank(w) and str(w).strip() != ":":
                        d, _ = to_date(w)
                        return d
    return None


def extract_stock(df: pd.DataFrame, profile_key: str, distributor: str, file_name: str, sheet_name: str,
                  header_row: int, run_date: dt.date, log: IssueLog) -> Tuple[pd.DataFrame, int]:
    prof = STOCK_PROFILES[profile_key]
    cols = prof["cols"]
    check_layout(df, header_row, prof["expected"], file_name, sheet_name, distributor, log)
    period = find_stock_period(df, profile_key)
    out: List[dict] = []
    n_read = 0
    mismatch_logged = False
    for tup in df.iloc[header_row + 1:].itertuples(index=True, name=None):
        idx, row = tup[0], tup[1:]
        code_raw = _get(row, cols["sku"])
        if is_blank(code_raw):
            continue                                              # sub-headers / spacing rows
        label = clean_text(code_raw).lower()
        if profile_key == "BMS_STOCK" and label.startswith(("brand", "total")):
            continue                                              # report grouping rows
        n_read += 1
        xl_row = idx + 1
        valid = True
        ctx = dict(file=file_name, sheet=sheet_name, row=xl_row, distributor=distributor)

        # ---- branch
        if profile_key == "SJP_STOCK":
            branch = SJP_GUDANG_BRANCH.get(clean_text(_get(row, cols["gudang"]))[:6], "")
            sheet_branch = SJP_STOCK_SHEET_BRANCH.get(sheet_name.strip())
            if sheet_branch and branch and sheet_branch != branch and not mismatch_logged:
                mismatch_logged = True
                log.add(WARNING, "SHEET_BRANCH_MISMATCH",
                        f"Nama sheet menunjuk {sheet_branch} tetapi kolom Gudang menunjuk {branch}; Gudang dipakai",
                        file=file_name, sheet=sheet_name, distributor=distributor)
        else:
            branch = distributor
        if branch not in BRANCH_ORDER:
            log.add(CRITICAL, "INVALID_BRANCH", f"Kode cabang tidak valid/tidak terbaca: '{branch}'",
                    original={"gudang": clean_text(_get(row, cols.get('gudang', 0)))} if "gudang" in cols else None, **ctx)
            valid = False

        sku, sci = text_id(code_raw)
        if sci:
            log.add(WARNING, "SCIENTIFIC_NOTATION", "Kode SKU berbentuk notasi ilmiah", original={"sku": code_raw}, **ctx)

        qty, unit, qissue = parse_stock_qty(_get(row, cols["qty"]))
        if qty is None:
            log.add(CRITICAL, "INVALID_QTY", "Qty stok bukan angka", original={"sku": sku, "qty": _get(row, cols["qty"])}, **ctx)
            valid = False
        else:
            if qissue == "DASH_AS_ZERO":
                log.add(INFO, "DASH_AS_ZERO", "Tanda '-' dibaca sebagai stok 0", original={"sku": sku}, **ctx)
            if qissue == "AMBIGUOUS_FORMAT":
                log.add(WARNING, "AMBIGUOUS_NUMBER", "Format angka stok ambigu", original={"sku": sku, "qty": _get(row, cols['qty'])}, **ctx)
            if unit and unit != "PCS":
                log.add(CRITICAL, "UNSUPPORTED_UNIT", f"Satuan stok '{unit}' bukan PCS, tidak dikonversi otomatis",
                        original={"sku": sku, "qty": _get(row, cols['qty'])}, **ctx)
                valid = False
            if qty < 0:
                log.add(WARNING, "NEGATIVE_STOCK", "Stok negatif", original={"sku": sku, "qty": qty}, **ctx)
        out.append({"distributor": distributor, "branch": branch, "sku_raw": sku, "qty": qty,
                    "stock_period": period, "source_file": file_name, "source_sheet": sheet_name,
                    "source_row": xl_row, "is_valid": valid})
    return pd.DataFrame(out, columns=RECORD_COLUMNS), n_read
