"""SKU resolution. Raw distributor code -> SKU Fix, with an explicit, auditable reason for every row.

Resolution order for a record of distributor D (family F):
  1. approved mapping row with scope D            (most specific)
  2. approved mapping row with scope F            (SJP / BMS / BGK / BLT)
  3. approved mapping row with scope '*'
  4. the raw code is itself a known SKU Fix value (already an HO code) -> VALID_HO_CODE
  otherwise UNMAPPED. Nothing is ever guessed; fuzzy matches are only *suggestions*.
"""
from __future__ import annotations

import difflib
import re
from typing import Dict, List, Set, Tuple

import pandas as pd

from config.distributors import FAMILY, VALID_SCOPES
from utils.normalization import clean_text, norm_key

MAPPING_COLUMNS = ["scope", "original_sku", "sku_fix", "status", "note", "updated_at"]
APPROVED = "approved"

MAPPED, VALID_HO, UNMAPPED = "MAPPED", "VALID_HO_CODE", "UNMAPPED"


def normalise_mapping(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in MAPPING_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out["scope"] = out["scope"].map(lambda v: "*" if clean_text(v) in ("", "*", "ALL") else clean_text(v).upper())
    out["original_sku"] = out["original_sku"].map(norm_key)
    out["sku_fix"] = out["sku_fix"].map(clean_text)
    out["status"] = out["status"].map(lambda v: clean_text(v).lower() or APPROVED)
    return out[MAPPING_COLUMNS]


def build_lookup(mapping: pd.DataFrame) -> Tuple[Dict[Tuple[str, str], str], Set[str], pd.DataFrame]:
    """Return (lookup, known_ho_codes, conflicts). Only approved rows participate."""
    m = normalise_mapping(mapping)
    m = m[(m["status"] == APPROVED) & (m["original_sku"] != "") & (m["sku_fix"] != "")]
    lookup: Dict[Tuple[str, str], str] = {}
    conflicts: List[dict] = []
    for scope, key, fix in m[["scope", "original_sku", "sku_fix"]].itertuples(index=False, name=None):
        prev = lookup.get((scope, key))
        if prev is not None and prev != fix:
            conflicts.append({"scope": scope, "original_sku": key, "sku_fix_a": prev, "sku_fix_b": fix})
            continue
        lookup[(scope, key)] = fix
    ho = {norm_key(v) for v in m["sku_fix"]}
    return lookup, ho, pd.DataFrame(conflicts, columns=["scope", "original_sku", "sku_fix_a", "sku_fix_b"])


def resolve_sku(distributor: str, sku_raw: str, lookup: dict, ho_codes: Set[str]) -> Tuple[str, str, str]:
    """Return (sku_fix, status, reason). sku_fix is '' when unresolved."""
    key = norm_key(sku_raw)
    if not key:
        return "", UNMAPPED, "kode kosong"
    for scope in (distributor, FAMILY.get(distributor, ""), "*"):
        hit = lookup.get((scope, key))
        if hit:
            return hit, MAPPED, f"scope {scope}"
    if key in ho_codes:
        return clean_text(sku_raw), VALID_HO, "kode sudah berupa SKU Fix"
    return "", UNMAPPED, "tidak ada di mapping"


def apply_mapping_to_records(records: pd.DataFrame, mapping: pd.DataFrame, passthrough: bool) -> pd.DataFrame:
    """Add sku_fix / mapping_status / mapping_reason. Re-runnable: always recomputed from sku_raw."""
    out = records.copy()
    if out.empty:
        for c in ("sku_fix", "mapping_status", "mapping_reason"):
            out[c] = pd.Series(dtype=object)
        return out
    lookup, ho, _ = build_lookup(mapping)
    pairs = out[["distributor", "sku_raw"]].drop_duplicates()
    res = {(d, s): resolve_sku(d, s, lookup, ho) for d, s in pairs.itertuples(index=False, name=None)}
    triples = [res[(d, s)] for d, s in zip(out["distributor"], out["sku_raw"])]
    out["sku_fix"] = [t[0] for t in triples]
    out["mapping_status"] = [t[1] for t in triples]
    out["mapping_reason"] = [t[2] for t in triples]
    if passthrough:       # 'as is' policy: keep the distributor code, status still says UNMAPPED
        miss = out["mapping_status"] == UNMAPPED
        out.loc[miss, "sku_fix"] = out.loc[miss, "sku_raw"]
    return out


def suggest_for_unmapped(unmapped: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Suggestions only (never applied automatically). Columns: distributor, original_sku, suggested_sku_fix, rule.

    Rules: (a) dropping a leading 'G' gives a known SKU Fix (BLT writes GBSR111002 for BSR111002);
           (b) close textual match to a known SKU Fix (difflib, ratio >= 0.88).
    """
    _, ho, _ = build_lookup(mapping)
    ho_list = sorted(ho)
    rows = []
    for dist, sku in unmapped[["distributor", "sku_raw"]].drop_duplicates().itertuples(index=False, name=None):
        k = norm_key(sku)
        if k.startswith("G") and k[1:] in ho:
            rows.append({"distributor": dist, "original_sku": sku, "suggested_sku_fix": k[1:], "rule": "buang awalan G"})
            continue
        close = difflib.get_close_matches(k, ho_list, n=1, cutoff=0.88)
        if close:
            rows.append({"distributor": dist, "original_sku": sku, "suggested_sku_fix": close[0], "rule": "mirip (fuzzy)"})
    return pd.DataFrame(rows, columns=["distributor", "original_sku", "suggested_sku_fix", "rule"])
