"""Reading .xlsx / .xls from bytes. Engine is chosen from the file signature, not the extension.

Some distributor exports declare ~1,000,000 formatted-but-empty rows; the .xlsx reader therefore stops
after MAX_BLANK_RUN consecutive blank rows instead of walking the declared range.
"""
from __future__ import annotations

import io
from typing import Dict, List

import pandas as pd
from openpyxl import load_workbook

from utils.duplicate_detector import file_hash

_XLSX_MAGIC = b"PK"
_XLS_MAGIC = b"\xd0\xcf\x11\xe0"
MAX_BLANK_RUN = 1000


class UnsupportedFileError(Exception):
    pass


def _blank_row(row) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in row)


class Book:
    """One uploaded workbook. Sheets are parsed lazily and cached as raw grids (no header, object dtype)."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data
        self.sha256 = file_hash(data)
        head = data[:8]
        self._xlsx = head.startswith(_XLSX_MAGIC)
        if self._xlsx:
            self._wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            self._names = list(self._wb.sheetnames)
        elif head.startswith(_XLS_MAGIC):
            self._xl = pd.ExcelFile(io.BytesIO(data), engine="xlrd")
            self._names = list(self._xl.sheet_names)
        else:
            raise UnsupportedFileError(f"{name}: bukan file Excel (.xlsx/.xls) yang valid")
        self._cache: Dict[str, pd.DataFrame] = {}

    @property
    def sheet_names(self) -> List[str]:
        return list(self._names)

    def _read_xlsx(self, name: str) -> pd.DataFrame:
        ws = self._wb[name]
        if not hasattr(ws, "iter_rows"):               # chart sheets
            return pd.DataFrame()
        rows, blank, last = [], 0, -1
        for row in ws.iter_rows(values_only=True):
            rows.append(row)
            if _blank_row(row):
                blank += 1
                if blank >= MAX_BLANK_RUN:
                    break
            else:
                blank, last = 0, len(rows) - 1
        rows = rows[:last + 1]
        if not rows:
            return pd.DataFrame()
        width = max(len(r) for r in rows)
        return pd.DataFrame([list(r) + [None] * (width - len(r)) for r in rows], dtype=object)

    def sheet(self, name: str) -> pd.DataFrame:
        if name not in self._cache:
            self._cache[name] = (self._read_xlsx(name) if self._xlsx
                                 else self._xl.parse(name, header=None, dtype=object))
        return self._cache[name]
