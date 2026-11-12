"""Value normalisation. Pure functions, no I/O, fully unit-tested."""
from __future__ import annotations

import datetime as dt
import math
import numbers
import re
from typing import Any, Optional, Tuple

import pandas as pd

_EXCEL_EPOCH = dt.datetime(1899, 12, 30)
_SERIAL_MIN, _SERIAL_MAX = 25569, 80000          # 1970 .. 2119
_SCI_RE = re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y",
                 "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S")


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _intify(f: float):
    return int(f) if float(f).is_integer() else f


def clean_text(v: Any) -> str:
    """Text for names/ids. Whole-number floats lose the '.0'; nothing else is altered."""
    if is_blank(v):
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, numbers.Real):
        f = float(v)
        return str(int(f)) if f.is_integer() else repr(f)
    return re.sub(r"\s+", " ", str(v).replace("\u00a0", " ")).strip()


def text_id(v: Any) -> Tuple[str, Optional[str]]:
    """Identifier as text. Returns (text, issue_code). Leading zeros are preserved."""
    t = clean_text(v)
    if t and _SCI_RE.match(t):
        return t, "SCIENTIFIC_NOTATION"
    return t, None


def norm_key(v: Any) -> str:
    """Key used for mapping look-ups (case-insensitive, whitespace-collapsed)."""
    return clean_text(v).upper()


def norm_header(v: Any) -> str:
    return re.sub(r"\s+", "", str(v)).lower() if not is_blank(v) else ""


def to_date(v: Any) -> Tuple[Optional[dt.date], Optional[str]]:
    """Convert any supported representation to a date. Text is read day-first (dd/mm/yyyy)."""
    if is_blank(v):
        return None, "MISSING_DATE"
    if isinstance(v, pd.Timestamp):
        return v.date(), None
    if isinstance(v, dt.datetime):
        return v.date(), None
    if isinstance(v, dt.date):
        return v, None
    if isinstance(v, bool):
        return None, "INVALID_DATE"
    if isinstance(v, numbers.Real):
        f = float(v)
        if math.isfinite(f) and _SERIAL_MIN <= f <= _SERIAL_MAX:
            return (_EXCEL_EPOCH + dt.timedelta(days=f)).date(), None
        return None, "INVALID_DATE"
    s = str(v).strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date(), None
        except ValueError:
            continue
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        return to_date(float(s))
    return None, "INVALID_DATE"


def to_number(v: Any) -> Tuple[Optional[float], Optional[str]]:
    """Numeric parse. Returns (value, issue_code). issue 'AMBIGUOUS_FORMAT' still returns a value."""
    if is_blank(v):
        return None, "MISSING"
    if isinstance(v, bool):
        return None, "INVALID"
    if isinstance(v, numbers.Real):
        f = float(v)
        return (_intify(f), None) if math.isfinite(f) else (None, "INVALID")
    s = str(v).strip().replace("\u00a0", "")
    if s in ("-", "–", "—"):
        return None, "DASH"
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)*", s):
        return None, "INVALID"
    sign = -1 if s.startswith("-") else 1
    body = s.lstrip("+-")
    if "." not in body and "," not in body:
        return sign * int(body), None
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", body):          # 1.234 / 1,234,567 -> thousands
        return sign * int(re.sub(r"[.,]", "", body)), "AMBIGUOUS_FORMAT"
    if "." in body and "," in body:                           # last separator is the decimal one
        dec = body[max(body.rfind("."), body.rfind(",")) + 1:]
        head = re.sub(r"[.,]", "", body[:max(body.rfind("."), body.rfind(","))])
        return sign * _intify(float(f"{head}.{dec}")), "AMBIGUOUS_FORMAT"
    return sign * _intify(float(body.replace(",", "."))), "AMBIGUOUS_FORMAT"


_STOCK_RE = re.compile(r"^\s*([+-]?[\d.,]+)\s*([A-Za-z]*)\s*$")


def parse_stock_qty(v: Any) -> Tuple[Optional[float], str, Optional[str]]:
    """Stock quantity that may carry a unit, e.g. '268 PCS'. Returns (qty, unit, issue_code).

    A lone dash means 'no stock' (qty 0, issue DASH_AS_ZERO).
    """
    if is_blank(v):
        return None, "", "MISSING"
    if isinstance(v, numbers.Real) and not isinstance(v, bool):
        q, issue = to_number(v)
        return q, "", issue
    s = str(v).strip()
    if s in ("-", "–", "—"):
        return 0, "", "DASH_AS_ZERO"
    m = _STOCK_RE.match(s)
    if not m:
        return None, "", "INVALID"
    q, issue = to_number(m.group(1))
    return q, m.group(2).upper(), issue
