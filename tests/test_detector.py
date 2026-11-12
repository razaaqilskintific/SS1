import pandas as pd
from config.sales_mapping import SALES_PROFILES
from processors.file_detector import apply_override, detect_sheet, filename_hint
from tests.helpers import grid


def bms_sales(prefix):
    return grid(23, [{0: f"{prefix}00012", 2: "X", 3: 1, 4: 2, 5: "1220114", 8: 1}],
                {0: "Customer Code", 1: "Customer Name", 2: "Salesman Code", 3: "Invoice Date",
                 4: "Invoice No", 5: "Item Code", 7: "PrincipalCode", 8: "CTN"})


def test_bms_distributor_from_customer_prefix_even_if_filename_misleading():
    d = detect_sheet("Jambi_Sales_1.xlsx", "Sheet1", bms_sales("BGO"))
    assert d.distributor == "MBO" and d.confidence == "Review" and d.status == "Needs confirmation"


def test_bms_agreement_is_high_confidence():
    d = detect_sheet("BGO_Sales_2.xlsx", "Sheet1", bms_sales("BGO"))
    assert (d.distributor, d.data_type, d.confidence, d.status) == ("MBO", "Sales", "High", "Detected")
    assert detect_sheet("SRLO_Sales_1.xlsx", "Sheet1", bms_sales("SLR")).distributor == "SRLO"


def test_renamed_headers_still_detected_by_position():
    exp = SALES_PROFILES["BLT_SALES"]["expected"]
    hdr = {p: (h if p in (0, 1, 5, 7, 9, 10, 15) else "renamed") for p, h in exp.items()}   # 1 of 8 renamed
    d = detect_sheet("BLT_Sales.xlsx", "Sheet1", grid(25, [{0: "x"}], hdr))
    assert d.profile == "BLT_SALES" and d.confidence == "High"


def test_half_matching_headers_need_confirmation_and_garbage_is_ignored():
    exp = SALES_PROFILES["BLT_SALES"]["expected"]
    hdr = {p: (h if p < 10 else "renamed") for p, h in exp.items()}
    assert detect_sheet("x.xlsx", "S", grid(25, [{0: "x"}], hdr)).status == "Needs confirmation"
    assert detect_sheet("x.xlsx", "S", grid(5, [{0: "a", 1: "b"}], {0: "foo", 1: "bar"})).status.startswith("Ignored")
    assert detect_sheet("x.xlsx", "S", pd.DataFrame()).status == "Ignored: sheet kosong"


def test_blt_stock_only_g2g_sheet_is_used():
    hdr = {1: "No", 2: "KODE", 3: "NAMA BARANG", 4: "ISI", 8: "QTY (PCS)"}
    df = grid(9, [{1: 1, 2: "G2G-1", 8: 1}], hdr)
    assert detect_sheet("BLT_Stock.xlsx", "G2G", df).status == "Detected"
    assert detect_sheet("BLT_Stock.xlsx", "UNZA", df).status.startswith("Ignored")


def test_manual_override():
    df = bms_sales("JMB")
    d = detect_sheet("weird.xlsx", "Sheet1", df)
    o = apply_override(d, df, "SRLO", "Sales")
    assert o.distributor == "SRLO" and o.confidence == "Manual" and o.profile == "BMS_SALES"


def test_filename_hint():
    assert filename_hint("Jambi_Stock_2.xls") == "JMB" and filename_hint("BGO_Stock_1.xls") == "MBO"
