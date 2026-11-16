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


def _blt_dets(*names):
    from processors.file_detector import Detection
    return [Detection("BLT.xlsx", n, profile="BLT_STOCK", distributor="BLT", data_type="Stock",
                      confidence="High", status="Detected", score=1.0, header_row=1) for n in names]


def test_blt_single_sheet_is_used_whatever_it_is_called():
    from processors.file_detector import resolve_blt_stock_sheets
    d = _blt_dets("Sheet1")
    resolve_blt_stock_sheets(d)
    assert d[0].status == "Detected"


def test_blt_multi_principal_workbook_uses_only_g2g_sheet():
    from processors.file_detector import resolve_blt_stock_sheets
    d = _blt_dets("UNZA", "G2G", "GARNIER")
    resolve_blt_stock_sheets(d)
    assert [x.status for x in d] == ["Ignored: sheet BLT bukan principal G2G", "Detected", "Ignored: sheet BLT bukan principal G2G"]


def test_blt_several_sheets_none_named_g2g_needs_confirmation_not_guessing():
    from processors.file_detector import resolve_blt_stock_sheets
    d = _blt_dets("A", "B")
    resolve_blt_stock_sheets(d)
    assert {x.status for x in d} == {"Needs confirmation"}


def test_real_blt_layout_is_detected_as_blt_stock_regardless_of_sheet_name():
    hdr = {1: "No", 2: "KODE", 3: "NAMA BARANG", 4: "ISI", 8: "QTY (PCS)"}
    d = detect_sheet("Lap Stock 14 November 2026, G2Gblt.xlsx", "Sheet1", grid(9, [{1: 1, 2: "G2G-1", 8: 1}], hdr))
    assert (d.profile, d.distributor, d.status) == ("BLT_STOCK", "BLT", "Detected")


def test_manual_override():
    df = bms_sales("JMB")
    d = detect_sheet("weird.xlsx", "Sheet1", df)
    o = apply_override(d, df, "SRLO", "Sales")
    assert o.distributor == "SRLO" and o.confidence == "Manual" and o.profile == "BMS_SALES"


def test_filename_hint():
    assert filename_hint("Jambi_Stock_2.xls") == "JMB" and filename_hint("BGO_Stock_1.xls") == "MBO"
