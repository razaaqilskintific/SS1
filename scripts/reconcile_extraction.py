"""Extraction-level reconciliation: engine output vs. an independent pandas read of the raw files.

Sums are taken straight from the raw columns (no shared code with the processors).
SKU-level reconciliation against the legacy workbook needs the Mapping export (next step).
"""
import glob, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from services.compilation_service import FileInput, compile_files

D = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"
P = lambda f: os.path.join(D, f)
num = lambda s: pd.to_numeric(s.astype(str).str.replace("PCS", "", regex=False).str.strip().replace({"-": "0"}), errors="coerce")

files = [FileInput(os.path.basename(p), open(p, "rb").read()) for p in sorted(glob.glob(D + "/*.xls*"))]
res = compile_files(files, run_date=dt.date(2026, 11, 12))
S, K = res.sales, res.stock
rows = []

def add(kind, name, eng_n, eng_q, raw_n, raw_q):
    rows.append({"kind": kind, "scope": name, "rows_engine": eng_n, "rows_raw": raw_n,
                 "qty_engine": eng_q, "qty_raw": raw_q,
                 "match": (eng_n == raw_n) and abs(float(eng_q) - float(raw_q)) < 1e-6})

# ---- sales
raw = pd.read_excel(P("SJP_Sales.xlsx"), dtype=object)
g = raw.iloc[:, 27].astype(str).str[:6].map({"311000": "PLM", "311001": "BTA", "311002": "LHT", "311003": "PRB"})
for b in ["PLM", "BTA", "LHT", "PRB"]:
    sub = S[(S.distributor == "SJP") & (S.dst_branch == b)]
    add("Sales", f"SJP/{b}", len(sub), sub.qty.sum(), int((g == b).sum()), pd.to_numeric(raw.iloc[:, 12][g == b]).sum())
for dist, fl in {"JMB": ["Jambi_Sales_1.xlsx", "Jambi_Sales_2.xlsx"], "MBO": ["BGO_Sales_1.xlsx", "BGO_Sales_2.xlsx"],
                 "SRLO": ["SRLO_Sales_1.xlsx", "SRLO_Sales_2.xlsx"]}.items():
    r = pd.concat([pd.read_excel(P(f), sheet_name="Sheet1", dtype=object) for f in fl])
    sub = S[S.distributor == dist]
    add("Sales", dist, len(sub), sub.qty.sum(), len(r), pd.to_numeric(r["CTN"]).sum())
r = pd.read_excel(P("BGK_Sales.xlsx"), sheet_name="Sheet1", dtype=object)
sub = S[S.distributor == "BGK"]
add("Sales", "BGK", len(sub), sub.qty.sum(), len(r), pd.to_numeric(r["QtyNonBonusPcs"]).sum())
r = pd.read_excel(P("BLT_Sales.xlsx"), dtype=object)
sub = S[S.distributor == "BLT"]
add("Sales", "BLT", len(sub), sub.qty.sum(), len(r), pd.to_numeric(r["Qty"]).sum())

# ---- stock
for sh, b in {"PLB1": "PLM", "BTA1": "BTA", "LHT": "LHT", "PBM": "PRB"}.items():
    r = pd.read_excel(P("SJP_Stock.xls"), sheet_name=sh, dtype=object)
    sub = K[(K.distributor == "SJP") & (K.branch == b)]
    add("Stock", f"SJP/{b}", len(sub), sub.qty.sum(), len(r), pd.to_numeric(r.iloc[:, 6]).sum())
def bms_stock(f):
    r = pd.read_excel(P(f), header=None, dtype=object)
    it = r.iloc[26:]
    it = it[it[0].astype(str).str.match(r"^\d+$")]
    return len(it), num(it[11]).fillna(0).sum()
for dist, fl in {"JMB": ["Jambi_Stock_1.xls", "Jambi_Stock_2.xls"], "MBO": ["BGO_Stock_1.xls", "BGO_Stock_2.xls"],
                 "SRLO": ["SRLO_Stock_1.xls", "SRLO_Stock_2.xls"]}.items():
    n = q = 0
    for f in fl:
        a, b = bms_stock(f); n += a; q += b
    sub = K[K.distributor == dist]
    add("Stock", dist, len(sub), sub.qty.sum(), n, q)
r = pd.read_excel(P("BGK_Stock.xls"), header=None, dtype=object).iloc[4:]
r = r[r[0].notna()]
sub = K[K.distributor == "BGK"]
add("Stock", "BGK", len(sub), sub.qty.sum(), len(r), num(r[4]).sum())
r = pd.read_excel(P("BLT_Stock.xlsx"), sheet_name="G2G", header=None, dtype=object).iloc[3:]
r = r[r[2].notna()]
sub = K[K.distributor == "BLT"]
add("Stock", "BLT/G2G", len(sub), sub.qty.sum(), len(r), pd.to_numeric(r[8]).sum())

out = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(out.to_string(index=False))
print("\nALL MATCH:", bool(out.match.all()), "| total sales rows", len(S), "| total stock rows", len(K))
out.to_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reconciliation_extraction.csv"), index=False)
