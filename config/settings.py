"""Application-wide settings. Everything business-specific lives in the other config modules."""
import os
from pathlib import Path

APP_NAME = "Daily Sales & Stock Compiler"
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DSSC_DB_PATH", str(BASE_DIR / "data" / "mapping.db"))

# Exact output structure (names and order are part of the business contract).
SALES_OUTPUT_COLUMNS = ["DST BRANCH", "SALES ID", "CUST ID", "CUST NAME",
                        "INVOICE DATE", "NO. INVOICE", "SKU Fix", "QTY"]
STOCK_OUTPUT_COLUMNS = ["QTY", "BRANCH", "SKU_Fix"]
DATE_NUMBER_FORMAT = "DD/MM/YYYY"   # one single date format for every distributor

# "passthrough_flagged": unmapped SKU keeps the distributor code in the SKU Fix column
#                        (the 'as is' behaviour of the old workbook) but is ALWAYS flagged.
# "block":               unmapped SKU blocks export until the mapping is completed.
UNMAPPED_POLICY = os.environ.get("DSSC_UNMAPPED_POLICY", "passthrough_flagged")

HEADER_SCAN_ROWS = 40       # rows scanned when looking for a header row
DETECT_HIGH = 0.85          # structural match >= this -> High confidence
DETECT_REVIEW = 0.50        # structural match >= this -> needs confirmation
