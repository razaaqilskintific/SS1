"""Where the mapping comes from.

Recommended setup: the mapping lives in a Google Sheet that you keep maintaining (it is shared as
'anyone with the link can view'). The app downloads it on demand (cached for 5 minutes in the UI layer).
Rows added inside the app are stored in the local layer (SQLite) and always win over the sheet.
"""
from __future__ import annotations

import re
import urllib.request

import pandas as pd

from processors.mapping_processor import normalise_mapping

_GS = re.compile(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)")


def gsheet_csv_url(url: str) -> str:
    """Turn a normal Google Sheets link into its CSV export link (keeps the tab via gid)."""
    url = url.strip()
    if "output=csv" in url or "format=csv" in url:
        return url
    m = _GS.search(url)
    if not m:
        raise ValueError("Link bukan link Google Sheets yang valid")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")


def fetch_bytes(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 (https only, user-supplied sheet)
        data = r.read()
    if data[:15].lower().startswith(b"<!doctype html") or data[:6].lower() == b"<html>":
        raise ValueError("Google Sheets mengembalikan halaman login: pastikan sheet dibagikan 'Siapa saja dengan link dapat melihat'")
    return data


def merge_mappings(base: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Local overrides replace base rows with the same (scope, original_sku). Status 'rejected' disables a base row."""
    if overrides is None or overrides.empty:
        return normalise_mapping(base)
    b, o = normalise_mapping(base), normalise_mapping(overrides)
    taken = set(zip(o["scope"], o["original_sku"]))
    keep = [k not in taken for k in zip(b["scope"], b["original_sku"])]
    return pd.concat([b[keep], o], ignore_index=True)
