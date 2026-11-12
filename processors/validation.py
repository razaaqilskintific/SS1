"""Validation primitives: issue log, severity policy and cross-record checks."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

CRITICAL, WARNING, INFO = "Critical", "Warning", "Info"
ISSUE_COLUMNS = ["severity", "code", "distributor", "file", "sheet", "row", "message", "original", "suggestion"]

# Codes that count as "missing required fields" / "invalid quantity" in the validation report.
MISSING_CODES = {"MISSING_CUST_ID", "MISSING_INVOICE", "MISSING_SALES_ID", "MISSING_SKU", "MISSING_DATE"}
INVALID_QTY_CODES = {"INVALID_QTY", "MISSING_QTY", "UNSUPPORTED_UNIT"}


@dataclass
class IssueLog:
    rows: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str, *, file: str = "", sheet: str = "",
            row: Optional[int] = None, distributor: str = "", original: Optional[dict] = None,
            suggestion: str = "") -> None:
        self.rows.append({
            "severity": severity, "code": code, "distributor": distributor, "file": file,
            "sheet": sheet, "row": row, "message": message,
            "original": "; ".join(f"{k}={v}" for k, v in (original or {}).items()),
            "suggestion": suggestion})

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=ISSUE_COLUMNS)


def month_of(d: dt.date) -> str:
    return f"{d.month:02d}/{d.year}"


def find_duplicate_transactions(sales: pd.DataFrame) -> pd.DataFrame:
    """Rows sharing the full transaction key. Rows are never removed, only reported.

    Identical lines on one invoice can be legitimate, so this is a warning for inspection.
    """
    if sales.empty:
        return sales.iloc[0:0]
    key = ["dst_branch", "sales_id", "cust_id", "invoice_date", "invoice_no", "sku_raw", "qty"]
    has_inv = sales["invoice_no"].astype(str).str.len() > 0
    sub = sales[has_inv]
    return sub[sub.duplicated(subset=key, keep=False)]
