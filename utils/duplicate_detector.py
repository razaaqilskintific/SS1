"""Duplicate *source* detection (identical files, identical data, heavy overlap)."""
from __future__ import annotations

import hashlib
from typing import Iterable, Set, Tuple

import pandas as pd


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def data_fingerprint(df: pd.DataFrame, cols: Iterable[str]) -> str:
    """Order-sensitive fingerprint of normalised records (not of the raw file bytes)."""
    cols = list(cols)
    payload = df[cols].astype(str).to_csv(index=False).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def key_set(df: pd.DataFrame, cols: Iterable[str]) -> Set[Tuple]:
    return set(map(tuple, df[list(cols)].astype(str).itertuples(index=False, name=None)))


def overlap_ratio(new_keys: Set[Tuple], existing_keys: Set[Tuple]) -> float:
    if not new_keys:
        return 0.0
    return len(new_keys & existing_keys) / len(new_keys)
