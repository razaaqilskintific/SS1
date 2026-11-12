"""Mapping persistence + import/export.

Storage architecture
--------------------
* Local / development: SQLite file (config.settings.DB_PATH).
* Streamlit Community Cloud: the container disk is NOT permanent. Mapping must live in an external
  store. `MappingStore` is the only class that touches storage; to move to Postgres/Supabase, implement the
  same methods (load, replace_all, upsert, set_status, delete, version, snapshot, restore) in a new class.
* Backup: every change bumps `version`; `export_xlsx()` produces the single maintainable mapping file.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import sqlite3
from typing import List, Tuple

import pandas as pd

from config.distributors import VALID_SCOPES
from processors.mapping_processor import APPROVED, MAPPING_COLUMNS, normalise_mapping
from utils.normalization import clean_text, norm_header

_ALIASES = {
    "scope": {"scope", "distributor", "dst", "berlakuuntuk"},
    "original_sku": {"kodeasli", "originalsku", "original", "kodedst", "skuasli", "kodedistributor"},
    "sku_fix": {"skufix", "sku_fix", "kodeho", "skuhasil"},
    "status": {"status"},
    "note": {"catatan", "note", "keterangan"},
    "nama": {"namadst", "namabarang", "namaproduk", "nama"},
}
_ALIASES = {k: {a.replace("_", "") for a in v} for k, v in _ALIASES.items()}
FILE_HEADERS = ["Scope", "Kode Asli", "SKU Fix", "Status", "Catatan"]


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _raw_frame(name: str, data: bytes) -> pd.DataFrame:
    if name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(data), header=None, dtype=object, keep_default_na=False, na_values=[""])
    return pd.read_excel(io.BytesIO(data), header=None, dtype=object)


def read_mapping_file(name: str, data: bytes) -> Tuple[pd.DataFrame, List[str]]:
    """Read a mapping file (CSV or Excel). Returns (valid rows, problems).

    * The header row is located automatically (a title row above it, as in the old workbook, is fine).
    * Accepted column names: Kode Asli / Kode DST, SKU Fix / Kode HO, Scope / Distributor, Status, Catatan,
      Nama DST (kept as note). Without a Scope column every row applies to all distributors ('*').
    * Identical duplicate rows are merged; the same original code with different SKU Fix is reported.
    """
    raw = _raw_frame(name, data)
    hdr, colmap = None, {}
    for i in range(min(15, len(raw))):
        m = {}
        for j, v in enumerate(raw.iloc[i]):
            h = norm_header(v).replace("_", "").replace(".", "")
            for target, aliases in _ALIASES.items():
                if h in aliases and target not in m.values():
                    m[j] = target
        if {"original_sku", "sku_fix"} <= set(m.values()):
            hdr, colmap = i, m
            break
    if hdr is None:
        return pd.DataFrame(columns=MAPPING_COLUMNS), ["Kolom wajib tidak ditemukan: perlu 'Kode Asli' (atau Kode DST) dan 'SKU Fix' (atau Kode HO)"]
    body = raw.iloc[hdr + 1:]
    frame = pd.DataFrame({t: body.iloc[:, j].values for j, t in colmap.items()})
    df = normalise_mapping(frame)
    if "note" in frame.columns:
        df["note"] = frame["note"].map(clean_text)
    elif "nama" in frame.columns:
        df["note"] = frame["nama"].map(clean_text)
    df["updated_at"] = _now()
    problems: List[str] = []
    xl_row = lambda i: hdr + 2 + i
    keep = df[(df["original_sku"] != "") | (df["sku_fix"] != "")]          # ignore fully blank lines
    bad_scope = ~keep["scope"].isin(VALID_SCOPES)
    blank = (keep["original_sku"] == "") | (keep["sku_fix"] == "")
    for i in keep.index[bad_scope]:
        problems.append(f"Baris {xl_row(i)}: scope '{keep.at[i, 'scope']}' tidak dikenal (pilihan: {', '.join(VALID_SCOPES)})")
    for i in keep.index[blank & ~bad_scope]:
        problems.append(f"Baris {xl_row(i)}: Kode Asli atau SKU Fix kosong")
    good = keep[~bad_scope & ~blank]
    conflicts = good.groupby(["scope", "original_sku"])["sku_fix"].nunique()
    for (sc, k) in conflicts[conflicts > 1].index:
        fixes = sorted(good[(good.scope == sc) & (good.original_sku == k)]["sku_fix"].unique())
        problems.append(f"Konflik: {sc}/{k} punya SKU Fix berbeda: {fixes}")
    exact = int(good.duplicated(["scope", "original_sku", "sku_fix"]).sum())
    if exact:
        problems.append(f"Info: {exact} baris duplikat identik digabung")
    return good.drop_duplicates(["scope", "original_sku", "sku_fix"], keep="last").reset_index(drop=True), problems


def import_legacy_mapping(data: bytes) -> pd.DataFrame:
    """Convert the old workbook's 'Mapping' sheet: Master Product BMS (D->F) and SJP (L->N) to long format."""
    raw = pd.read_excel(io.BytesIO(data), sheet_name="Mapping", header=None, dtype=object)
    rows = []
    for scope, c_dst, c_ho in (("BMS", 3, 5), ("SJP", 11, 13)):
        for _, r in raw.iloc[2:].iterrows():
            o, f = clean_text(r.iloc[c_dst]), clean_text(r.iloc[c_ho])
            if o and f:
                rows.append({"scope": scope, "original_sku": o, "sku_fix": f, "status": APPROVED,
                             "note": "import workbook lama", "updated_at": _now()})
    return normalise_mapping(pd.DataFrame(rows, columns=MAPPING_COLUMNS)).drop_duplicates(["scope", "original_sku"])


def mapping_to_xlsx(df: pd.DataFrame) -> bytes:
    out = df.rename(columns=dict(zip(["scope", "original_sku", "sku_fix", "status", "note"], FILE_HEADERS)))
    out = out[FILE_HEADERS]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        out.to_excel(xw, index=False, sheet_name="Mapping")
        ws = xw.sheets["Mapping"]
        for col in "ABCDE":
            ws.column_dimensions[col].width = 22
        for row in ws.iter_rows(min_row=2, max_col=3):
            for cell in row:
                cell.number_format = "@"
    return buf.getvalue()


class MappingStore:
    def __init__(self, path: str):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS mapping(scope TEXT, original_sku TEXT, sku_fix TEXT, status TEXT,
                note TEXT, updated_at TEXT, PRIMARY KEY(scope, original_sku));
            CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER, updated_at TEXT, note TEXT);
            INSERT OR IGNORE INTO meta VALUES(1, 0, '', '');
            CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, note TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS audit(ts TEXT, action TEXT, detail TEXT);
            """)

    def _conn(self):
        return sqlite3.connect(self.path)

    def _bump(self, c, action: str, detail: str) -> None:
        c.execute("UPDATE meta SET version=version+1, updated_at=?, note=? WHERE id=1", (_now(), detail))
        c.execute("INSERT INTO audit VALUES(?,?,?)", (_now(), action, detail))

    def load(self) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query("SELECT scope, original_sku, sku_fix, status, note, updated_at FROM mapping "
                                     "ORDER BY scope, original_sku", c)

    def version(self) -> dict:
        with self._conn() as c:
            v, ts, note = c.execute("SELECT version, updated_at, note FROM meta WHERE id=1").fetchone()
        return {"version": v, "updated_at": ts, "note": note}

    def upsert(self, df: pd.DataFrame, note: str = "upsert") -> int:
        df = normalise_mapping(df)
        df["updated_at"] = _now()
        with self._conn() as c:
            c.executemany("INSERT OR REPLACE INTO mapping VALUES(?,?,?,?,?,?)",
                          df[MAPPING_COLUMNS].itertuples(index=False, name=None))
            self._bump(c, "upsert", f"{note}: {len(df)} baris")
        return len(df)

    def replace_all(self, df: pd.DataFrame, note: str = "replace") -> int:
        self.snapshot(f"sebelum {note}")
        with self._conn() as c:
            c.execute("DELETE FROM mapping")
        n = self.upsert(df, note)
        return n

    def set_status(self, scope: str, original_sku: str, status: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE mapping SET status=?, updated_at=? WHERE scope=? AND original_sku=?",
                      (status, _now(), scope, original_sku))
            self._bump(c, "status", f"{scope}/{original_sku} -> {status}")

    def delete(self, scope: str, original_sku: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM mapping WHERE scope=? AND original_sku=?", (scope, original_sku))
            self._bump(c, "delete", f"{scope}/{original_sku}")

    def snapshot(self, note: str = "") -> int:
        payload = self.load().to_json(orient="records")
        with self._conn() as c:
            cur = c.execute("INSERT INTO snapshots(created_at, note, payload) VALUES(?,?,?)", (_now(), note, payload))
            return cur.lastrowid

    def snapshots(self) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query("SELECT id, created_at, note FROM snapshots ORDER BY id DESC", c)

    def restore(self, snapshot_id: int) -> int:
        with self._conn() as c:
            (payload,) = c.execute("SELECT payload FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return self.replace_all(pd.read_json(io.StringIO(payload), orient="records", dtype=False), f"restore #{snapshot_id}")

    def audit(self, limit: int = 200) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query(f"SELECT ts, action, detail FROM audit ORDER BY ts DESC LIMIT {int(limit)}", c)

    def export_xlsx(self) -> bytes:
        return mapping_to_xlsx(self.load())
