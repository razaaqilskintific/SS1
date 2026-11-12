"""Distributor reference data. Edit here, never inside processing code."""

DISTRIBUTOR_ORDER = ["SJP", "JMB", "MBO", "SRLO", "BGK", "BLT"]
BRANCH_ORDER = ["PLM", "BTA", "LHT", "PRB", "PLM BS", "JMB", "MBO", "SRLO", "BGK", "BLT"]

# Mapping scopes: a mapping row can apply to one distributor, a family, or everything ("*").
FAMILY = {"SJP": "SJP", "JMB": "BMS", "MBO": "BMS", "SRLO": "BMS", "BGK": "BGK", "BLT": "BLT"}
VALID_SCOPES = ["*", "SJP", "BMS", "BGK", "BLT", "JMB", "MBO", "SRLO"]

# SJP: branch comes from the first 6 characters of the warehouse (Gudang) text.
SJP_GUDANG_BRANCH = {"311000": "PLM", "311001": "BTA", "311002": "LHT", "311003": "PRB"}
SJP_UNKNOWN_BRANCH = "PLM BS"          # same fallback as the legacy workbook (always flagged)
SJP_STOCK_SHEET_BRANCH = {"PLB1": "PLM", "BTA1": "BTA", "LHT": "LHT", "PBM": "PRB"}  # cross-check only

# BMS family (Jambi / Bungo / Sarolangun). Distributor files call Bungo "BGO"; output code is MBO.
BMS_CUSTOMER_PREFIX = {"JMB": "JMB", "BGO": "MBO", "SLR": "SRLO"}
BMS_STOCK_KEYWORDS = [("SAROLANGUN", "SRLO"), ("BUNGO", "MBO"), ("JAMBI", "JMB")]

FILENAME_HINTS = [("sjp", "SJP"), ("jambi", "JMB"), ("jmb", "JMB"), ("bgo", "MBO"),
                  ("mbo", "MBO"), ("srlo", "SRLO"), ("bgk", "BGK"), ("blt", "BLT")]

# BLT stock workbook has one sheet per principal. Only these sheets are read.
BLT_STOCK_SHEETS = ["G2G"]

PROFILE_BY = {
    ("SJP", "Sales"): "SJP_SALES", ("BMS", "Sales"): "BMS_SALES",
    ("BGK", "Sales"): "BGK_SALES", ("BLT", "Sales"): "BLT_SALES",
    ("SJP", "Stock"): "SJP_STOCK", ("BMS", "Stock"): "BMS_STOCK",
    ("BGK", "Stock"): "BGK_STOCK", ("BLT", "Stock"): "BLT_STOCK",
}
