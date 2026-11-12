"""Final Excel outputs. Standardised columns only: no internal metadata may leak into these files."""
from __future__ import annotations

import io
from typing import List

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from config import settings
from config.settings import SALES_OUTPUT_COLUMNS, STOCK_OUTPUT_COLUMNS
from processors.mapping_processor import UNMAPPED
from services.compilation_service import CompilationResult

_FONT = Font(name="Arial", size=10)
_HEAD = Font(name="Arial", size=10, bold=True)
_FILL = PatternFill("solid", fgColor="E8EAED")
_TEXT_COLS = {"DST BRANCH", "SALES ID", "CUST ID", "CUST NAME", "NO. INVOICE", "SKU Fix", "BRANCH", "SKU_Fix"}


class BlockedByCriticalErrors(Exception):
    """Raised when export is attempted while blocking issues exist and exclusion was not confirmed."""


def sales_output(res: CompilationResult, exclude_invalid: bool = False) -> pd.DataFrame:
    df = res.sales
    _guard(df, exclude_invalid)
    df = df[df["is_valid"]] if exclude_invalid else df
    out = pd.DataFrame({
        "DST BRANCH": df["dst_branch"], "SALES ID": df["sales_id"], "CUST ID": df["cust_id"],
        "CUST NAME": df["cust_name"], "INVOICE DATE": df["invoice_date"], "NO. INVOICE": df["invoice_no"],
        "SKU Fix": df["sku_fix"], "QTY": df["qty"]})
    return out[SALES_OUTPUT_COLUMNS].reset_index(drop=True)


def stock_output(res: CompilationResult, exclude_invalid: bool = False) -> pd.DataFrame:
    df = res.stock
    _guard(df, exclude_invalid)
    df = df[df["is_valid"]] if exclude_invalid else df
    out = pd.DataFrame({"QTY": df["qty"], "BRANCH": df["branch"], "SKU_Fix": df["sku_fix"]})
    return out[STOCK_OUTPUT_COLUMNS].reset_index(drop=True)


def _guard(df: pd.DataFrame, exclude_invalid: bool) -> None:
    if df.empty:
        return
    n_bad = int((~df["is_valid"]).sum())
    if n_bad and not exclude_invalid:
        raise BlockedByCriticalErrors(f"{n_bad} baris memiliki error kritis. Perbaiki atau pilih 'keluarkan baris error'.")
    if settings.UNMAPPED_POLICY == "block" and (df["mapping_status"] == UNMAPPED).any():
        raise BlockedByCriticalErrors("Masih ada SKU yang belum ter-mapping (kebijakan: blok).")


def _write_sheet(ws, df: pd.DataFrame) -> None:
    ws.append(list(df.columns))
    for c in ws[1]:
        c.font, c.fill, c.alignment = _HEAD, _FILL, Alignment(vertical="center")
    for row in df.itertuples(index=False, name=None):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
    for j, col in enumerate(df.columns, start=1):
        width = max([len(str(col))] + [len(str(v)) for v in df[col].head(500)]) + 2
        ws.column_dimensions[ws.cell(1, j).column_letter].width = min(max(width, 10), 45)
        for r in range(2, ws.max_row + 1):
            cell = ws.cell(r, j)
            cell.font = _FONT
            if col in _TEXT_COLS:
                cell.number_format = "@"
            elif col == "INVOICE DATE":
                cell.number_format = settings.DATE_NUMBER_FORMAT
    ws.freeze_panes = "A2"


def _book(frames: List[tuple]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for title, df in frames:
        _write_sheet(wb.create_sheet(title), df)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def sales_workbook(res, exclude_invalid=False) -> bytes:
    return _book([("Sales Summary", sales_output(res, exclude_invalid))])


def stock_workbook(res, exclude_invalid=False) -> bytes:
    return _book([("Stock Summary", stock_output(res, exclude_invalid))])


def combined_workbook(res, exclude_invalid=False) -> bytes:
    return _book([("Sales Summary", sales_output(res, exclude_invalid)),
                  ("Stock Summary", stock_output(res, exclude_invalid))])
