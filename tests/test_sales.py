import datetime as dt
import pytest
from config.sales_mapping import SALES_PROFILES
from processors.sales_processor import extract_sales
from tests.helpers import RUN, grid, new_log


def sjp_header():
    return {pos: h for pos, h in SALES_PROFILES["SJP_SALES"]["expected"].items()}


def run(profile, dist, df, hdr=0):
    log = new_log()
    rec, n = extract_sales(df, profile, dist, "f.xlsx", "Sheet1", hdr, RUN, log)
    return rec, n, log.to_df()


def test_sjp_row_and_branch_from_gudang_and_serial_date():
    row = {0: "3110000062", 1: "ZEST. MM", 3: "311000SR47", 5: 46332, 6: "JAJ31261100515", 7: "376201",
           12: 2, 27: "311003 - GUDANG BAD STOCK"}
    df = grid(29, [row], {0: "Outlet", 1: "Nama Outlet", 3: "Sales ID", 5: "Tgl Faktur", 6: "No Faktur",
                          7: "PCODE", 9: "Unit ID", 10: "Qty", 11: "Unit ID", 12: "Qty",
                          26: "Supplier Name", 27: "Nama Gudang"})
    rec, n, iss = run("SJP_SALES", "SJP", df)
    r = rec.iloc[0]
    assert (r.dst_branch, r.sales_id, r.cust_id, r.invoice_date, r.invoice_no, r.sku_raw, r.qty) == \
           ("PRB", "311000SR47", "3110000062", dt.date(2026, 11, 6), "JAJ31261100515", "376201", 2)
    assert r.source_row == 2 and bool(r.is_valid)
    assert iss.empty


def test_sjp_unknown_gudang_flagged_not_silent():
    log = new_log()
    full = grid(29, [{0: "1", 3: "S", 5: 46332, 6: "X1", 7: "376201", 12: 1, 27: "999999 - X"}], {0: "Outlet"})
    rec, _ = extract_sales(full, "SJP_SALES", "SJP", "f", "s", 0, RUN, log)
    assert rec.iloc[0].dst_branch == "PLM BS"
    assert "UNKNOWN_BRANCH" in set(log.to_df().code)


def test_bms_uses_ctn_and_text_invoice():
    df = grid(23, [{0: "JMB00012", 1: "A.R", 2: "JMB007", 3: dt.datetime(2026, 11, 7), 4: 78126039913,
                    5: "1220114", 8: 3}],
              {0: "Customer Code", 8: "CTN"})
    rec, _, iss = run("BMS_SALES", "JMB", df)
    r = rec.iloc[0]
    assert r.dst_branch == "JMB" and r.invoice_no == "78126039913" and r.qty == 3 and r.cust_id == "JMB00012"


def test_bgk_uses_qty_non_bonus_and_missing_invoice_is_warning_but_kept():
    df = grid(24, [{0: dt.datetime(2026, 11, 13), 3: "P0305", 5: None, 6: "BK1", 7: "TOKO", 9: "G2G-72", 11: 6}],
              {0: "Tanggal", 11: "QtyNonBonusPcs"})
    rec, _, iss = run("BGK_SALES", "BGK", df)
    assert len(rec) == 1 and bool(rec.iloc[0].is_valid) and rec.iloc[0].qty == 6
    codes = set(iss.code)
    assert {"MISSING_INVOICE", "FUTURE_DATE"} <= codes
    assert set(iss[iss.code == "MISSING_INVOICE"].severity) == {"Warning"}


def test_blt_text_date_dayfirst_and_int_customer_as_text():
    df = grid(25, [{0: "JL.26-61056", 1: "02/11/2026", 5: "GBSR111002", 7: "01A03", 9: 22600, 10: "TOKO", 16: 4}],
              {0: "No. Faktur", 16: "Qty"})
    rec, _, _ = run("BLT_SALES", "BLT", df)
    r = rec.iloc[0]
    assert r.invoice_date == dt.date(2026, 11, 2) and r.cust_id == "22600" and r.sku_raw == "GBSR111002"


def test_zero_and_negative_qty_kept_with_flags():
    df = grid(25, [{0: "A", 1: "02/11/2026", 5: "G2G-1", 9: 1, 16: 0}, {0: "B", 1: "02/11/2026", 5: "G2G-1", 9: 1, 16: -2}],
              {0: "No. Faktur"})
    rec, _, iss = run("BLT_SALES", "BLT", df)
    assert len(rec) == 2 and rec.is_valid.all()
    assert {"ZERO_QTY", "NEGATIVE_QTY"} <= set(iss.code)


def test_invalid_qty_and_missing_sku_are_critical_and_row_invalid():
    df = grid(25, [{0: "A", 1: "02/11/2026", 5: "", 9: 1, 16: "abc"}], {0: "No. Faktur"})
    rec, _, iss = run("BLT_SALES", "BLT", df)
    assert not bool(rec.iloc[0].is_valid)
    assert {"INVALID_QTY", "MISSING_SKU"} <= set(iss[iss.severity == "Critical"].code)


def test_empty_rows_skipped_and_source_row_numbers_are_excel_rows():
    df = grid(25, [{}, {0: "A", 1: "02/11/2026", 5: "G2G-1", 9: 1, 16: 1}], {0: "No. Faktur"})
    rec, n, _ = run("BLT_SALES", "BLT", df)
    assert n == 1 and rec.iloc[0].source_row == 3


def test_layout_shift_is_reported():
    df = grid(25, [{0: "A", 1: "02/11/2026", 5: "G2G-1", 9: 1, 16: 1}], {0: "Faktur?", 16: "Qty"})
    _, _, iss = run("BLT_SALES", "BLT", df)
    assert "LAYOUT_DIFFERS" in set(iss.code)
