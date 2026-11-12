"""Sales extraction. One independent code path per layout, driven by config/sales_mapping.py."""
from __future__ import annotations

import datetime as dt
from typing import Any, List, Tuple

import pandas as pd

from config.distributors import BRANCH_ORDER, SJP_GUDANG_BRANCH, SJP_UNKNOWN_BRANCH
from config.sales_mapping import SALES_PROFILES
from processors.validation import CRITICAL, INFO, WARNING, IssueLog
from utils.normalization import clean_text, is_blank, norm_header, text_id, to_date, to_number

RECORD_COLUMNS = ["distributor", "dst_branch", "sales_id", "cust_id", "cust_name", "invoice_date",
                  "invoice_no", "sku_raw", "qty", "source_file", "source_sheet", "source_row", "is_valid"]


def _get(row: tuple, col: int) -> Any:
    return row[col] if col < len(row) else None


def _sjp_branch(gudang: Any) -> Tuple[str, bool]:
    prefix = clean_text(gudang)[:6]
    b = SJP_GUDANG_BRANCH.get(prefix)
    return (b, True) if b else (SJP_UNKNOWN_BRANCH, False)


def check_layout(df: pd.DataFrame, header_row: int, expected: dict, file_name: str, sheet: str,
                 distributor: str, log: IssueLog) -> None:
    """Warn when headers are not where the configuration expects them (renames are fine, shifts are not)."""
    row = df.iloc[header_row]
    bad = [f"kol {p + 1}: '{h}' != '{norm_header(row.iloc[p]) if p < len(row) else '-'}'"
           for p, h in expected.items() if p >= len(row) or norm_header(row.iloc[p]) != h]
    if bad:
        log.add(WARNING, "LAYOUT_DIFFERS", f"Header berbeda dari konfigurasi ({len(bad)} kolom): " + "; ".join(bad[:4]),
                file=file_name, sheet=sheet, row=header_row + 1, distributor=distributor,
                suggestion="Pastikan posisi kolom tidak bergeser; nama header yang berubah tidak masalah.")


def extract_sales(df: pd.DataFrame, profile_key: str, distributor: str, file_name: str, sheet_name: str,
                  header_row: int, run_date: dt.date, log: IssueLog) -> Tuple[pd.DataFrame, int]:
    """Return (records, source_rows_read). Source data is never modified."""
    prof = SALES_PROFILES[profile_key]
    cols = prof["cols"]
    check_layout(df, header_row, prof["expected"], file_name, sheet_name, distributor, log)
    out: List[dict] = []
    n_read = 0
    body = df.iloc[header_row + 1:]
    for tup in body.itertuples(index=True, name=None):
        idx, row = tup[0], tup[1:]
        raw = {k: _get(row, c) for k, c in cols.items()}
        if all(is_blank(raw[k]) for k in ("cust_id", "invoice_date", "invoice_no", "sku", "qty")):
            continue                                   # genuinely empty row
        n_read += 1
        xl_row = idx + 1
        valid = True
        ctx = dict(file=file_name, sheet=sheet_name, row=xl_row, distributor=distributor)

        # ---- branch
        if profile_key == "SJP_SALES":
            branch, known = _sjp_branch(_get(row, prof["gudang_col"]))
            if not known:
                log.add(WARNING, "UNKNOWN_BRANCH", f"Awalan gudang tidak dikenal, cabang diisi '{branch}'",
                        original={"gudang": clean_text(_get(row, prof['gudang_col']))},
                        suggestion="Tambahkan awalan gudang di config/distributors.py", **ctx)
        else:
            branch = distributor
        if branch not in BRANCH_ORDER:
            log.add(CRITICAL, "INVALID_BRANCH", f"Kode cabang tidak valid: '{branch}'", **ctx)
            valid = False

        # ---- identifiers (always text, leading zeros preserved)
        sales_id, _ = text_id(raw["sales_id"])
        cust_id, sci1 = text_id(raw["cust_id"])
        invoice_no, sci2 = text_id(raw["invoice_no"])
        sku, sci3 = text_id(raw["sku"])
        cust_name = clean_text(raw["cust_name"])
        for code, issue in (("cust_id", sci1), ("invoice_no", sci2), ("sku", sci3)):
            if issue:
                log.add(WARNING, "SCIENTIFIC_NOTATION", f"Kolom {code} berbentuk notasi ilmiah",
                        original={code: raw[code]}, **ctx)
        if not sales_id:
            log.add(WARNING, "MISSING_SALES_ID", "Sales ID kosong", **ctx)
        if not cust_id:
            log.add(WARNING, "MISSING_CUST_ID", "Customer ID kosong", **ctx)
        if not invoice_no:
            log.add(WARNING, "MISSING_INVOICE", "Nomor invoice kosong (baris tetap diikutkan)",
                    original={"cust": cust_id, "sku": sku, "tanggal": raw["invoice_date"]}, **ctx)
        if not sku:
            log.add(CRITICAL, "MISSING_SKU", "Kode SKU kosong", original={"invoice": invoice_no}, **ctx)
            valid = False

        # ---- date
        d, dissue = to_date(raw["invoice_date"])
        if d is None:
            log.add(CRITICAL, "INVALID_DATE" if dissue != "MISSING_DATE" else "MISSING_DATE",
                    "Tanggal invoice tidak valid/kosong", original={"tanggal": raw["invoice_date"]}, **ctx)
            valid = False
        elif d > run_date:
            log.add(WARNING, "FUTURE_DATE", f"Tanggal invoice {d:%d/%m/%Y} setelah tanggal proses {run_date:%d/%m/%Y}",
                    original={"invoice": invoice_no}, **ctx)

        # ---- quantity
        qty, qissue = to_number(raw["qty"])
        if qty is None:
            log.add(CRITICAL, "INVALID_QTY", "Qty bukan angka", original={"qty": raw["qty"]}, **ctx)
            valid = False
        else:
            if qissue == "AMBIGUOUS_FORMAT":
                log.add(WARNING, "AMBIGUOUS_NUMBER", "Format angka qty ambigu", original={"qty": raw["qty"]}, **ctx)
            if qty == 0:
                log.add(WARNING, "ZERO_QTY", "Qty = 0 (baris tetap diikutkan)",
                        original={"invoice": invoice_no, "sku": sku}, **ctx)
            elif qty < 0:
                log.add(INFO, "NEGATIVE_QTY", "Qty negatif (retur)", original={"invoice": invoice_no, "qty": qty}, **ctx)

        out.append({"distributor": distributor, "dst_branch": branch, "sales_id": sales_id, "cust_id": cust_id,
                    "cust_name": cust_name, "invoice_date": d, "invoice_no": invoice_no, "sku_raw": sku,
                    "qty": qty, "source_file": file_name, "source_sheet": sheet_name,
                    "source_row": xl_row, "is_valid": valid})
    return pd.DataFrame(out, columns=RECORD_COLUMNS), n_read
