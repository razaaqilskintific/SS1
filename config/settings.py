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

# ---- branding (replace the files in assets/ with your own; same names, no code change needed)
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"       # shown at the top of the sidebar, above the menu
ICON_PATH = ASSETS_DIR / "icon.png"       # optional small icon when the sidebar is collapsed
BANNER_PATH = ASSETS_DIR / "banner.jpg"   # wide photo shown under every page title
BANNER_HEIGHT = 150                       # px, the photo is centre-cropped to a wide strip
PAGE_ICON = "📊"                          # browser-tab icon
