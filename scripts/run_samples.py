import sys, glob, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
from services.compilation_service import FileInput, compile_files, compute_stats
d = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"
files = [FileInput(os.path.basename(p), open(p, "rb").read()) for p in sorted(glob.glob(d + "/*.xls*"))]
res = compile_files(files, run_date=dt.date(2026, 11, 12))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
print(res.detections.to_string())
print(compute_stats(res))
print(res.issues.groupby(["severity", "code"]).size())
