"""File / sheet detection using several signals: structure fingerprint, content, file name."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import settings
from config.distributors import (BLT_STOCK_SHEETS, BMS_CUSTOMER_PREFIX, BMS_STOCK_KEYWORDS,
                                 FAMILY, FILENAME_HINTS, PROFILE_BY)
from config.sales_mapping import SALES_PROFILES
from config.stock_mapping import STOCK_PROFILES
from utils.normalization import clean_text, is_blank, norm_header

ALL_PROFILES = {**SALES_PROFILES, **STOCK_PROFILES}
DATA_TYPE = {k: ("Sales" if k in SALES_PROFILES else "Stock") for k in ALL_PROFILES}


@dataclass
class Detection:
    file_name: str
    sheet_name: str
    profile: Optional[str] = None
    distributor: str = ""
    data_type: str = ""
    confidence: str = ""          # High / Review / ""
    status: str = ""              # Detected / Needs confirmation / Ignored: <reason>
    score: float = 0.0
    header_row: Optional[int] = None
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def processable(self) -> bool:
        return self.profile is not None and not self.status.startswith("Ignored")


def score_profile(df: pd.DataFrame, expected: Dict[int, str]) -> Tuple[float, Optional[int]]:
    """Best fraction of expected headers found at their expected positions in any of the first rows."""
    best, best_row = 0.0, None
    head = df.head(settings.HEADER_SCAN_ROWS)
    for r in range(len(head)):
        row = head.iloc[r]
        hits = sum(1 for pos, h in expected.items()
                   if pos < len(row) and norm_header(row.iloc[pos]) == h)
        s = hits / len(expected)
        if s > best:
            best, best_row = s, r
    return best, best_row


def filename_hint(file_name: str) -> str:
    low = file_name.lower()
    for token, dist in FILENAME_HINTS:
        if token in low:
            return dist
    return ""


def bms_distributor_from_sales(df: pd.DataFrame, header_row: int) -> str:
    col = SALES_PROFILES["BMS_SALES"]["customer_col"]
    vals = df.iloc[header_row + 1: header_row + 301, col].dropna().astype(str).str.strip().str.upper()
    counts: Dict[str, int] = {}
    for v in vals:
        d = BMS_CUSTOMER_PREFIX.get(v[:3])
        if d:
            counts[d] = counts.get(d, 0) + 1
    return max(counts, key=counts.get) if counts else ""


def bms_distributor_from_stock(df: pd.DataFrame) -> str:
    text = " ".join(clean_text(v).upper() for v in df.head(30).to_numpy().ravel() if not is_blank(v))
    for kw, dist in BMS_STOCK_KEYWORDS:
        if kw in text:
            return dist
    return ""


def _resolve_distributor(family: str, data_type: str, df: pd.DataFrame, header_row: int,
                         hint: str) -> Tuple[str, str, str]:
    """Return (distributor, confidence, note)."""
    if family != "BMS":
        note = ""
        if hint and FAMILY.get(hint) != family:
            return family, "Review", f"Nama file mengarah ke {hint}, isi file cocok {family}"
        return family, "High", note
    content = (bms_distributor_from_sales(df, header_row) if data_type == "Sales"
               else bms_distributor_from_stock(df))
    if content and hint and content != hint:
        return content, "Review", f"Isi file = {content}, nama file mengarah ke {hint}"
    if content:
        return content, "High", ""
    if hint and FAMILY.get(hint) == "BMS":
        return hint, "Review", "Distributor hanya dari nama file"
    return "", "Review", "Distributor tidak dapat ditentukan"


def detect_sheet(file_name: str, sheet_name: str, df: pd.DataFrame) -> Detection:
    det = Detection(file_name=file_name, sheet_name=sheet_name)
    if df is None or df.empty or df.dropna(how="all").empty:
        det.status = "Ignored: sheet kosong"
        return det
    scored = []
    for key, prof in ALL_PROFILES.items():
        s, r = score_profile(df, prof["expected"])
        scored.append((s, key, r))
    scored.sort(reverse=True)
    best, key, hrow = scored[0]
    if best < settings.DETECT_REVIEW:
        det.status = "Ignored: struktur tidak dikenali"
        det.score = round(best, 2)
        return det
    prof = ALL_PROFILES[key]
    dtype = DATA_TYPE[key]
    dist, conf, note = _resolve_distributor(prof["family"], dtype, df, hrow, filename_hint(file_name))
    if best < settings.DETECT_HIGH:
        conf = "Review"
        note = (note + "; " if note else "") + f"Kecocokan struktur kolom {best:.0%}"
    det.profile, det.data_type, det.distributor = key, dtype, dist
    det.confidence, det.score, det.header_row, det.notes = conf, round(best, 2), hrow, note
    det.status = "Detected" if conf == "High" else "Needs confirmation"
    if key == "BLT_STOCK" and sheet_name.strip().lower() not in [s.lower() for s in BLT_STOCK_SHEETS]:
        det.status = "Ignored: sheet BLT bukan principal G2G"
    return det


def apply_override(det: Detection, df: pd.DataFrame, distributor: str, data_type: str) -> Detection:
    """Manual correction: the user states distributor + type; header row is re-located."""
    family = FAMILY[distributor]
    key = PROFILE_BY[(family, data_type)]
    score, hrow = score_profile(df, ALL_PROFILES[key]["expected"])
    return Detection(file_name=det.file_name, sheet_name=det.sheet_name, profile=key,
                     distributor=distributor, data_type=data_type, confidence="Manual",
                     status="Detected", score=round(score, 2), header_row=hrow or 0,
                     notes="Dikoreksi manual")
