import datetime as dt
from processors.stock_processor import extract_stock, find_stock_period
from tests.helpers import RUN, grid, new_log


def run(profile, dist, df, hdr, sheet="S"):
    log = new_log()
    rec, n = extract_stock(df, profile, dist, "f.xls", sheet, hdr, RUN, log)
    return rec, n, log.to_df()


def test_sjp_branch_from_gudang_and_sheet_mismatch_warning():
    df = grid(15, [{0: "377030", 6: 301, 14: "311003GS - 311003 - GUDANG BAIK"}],
              {0: "ItemID", 6: "Ending Balance(Qty)", 14: "Gudang"})
    rec, _, iss = run("SJP_STOCK", "SJP", df, 0, sheet="PLB1")
    assert rec.iloc[0].branch == "PRB" and rec.iloc[0].qty == 301
    assert "SHEET_BRANCH_MISMATCH" in set(iss.code)


def test_bms_available_qty_skips_brand_rows_and_dash_is_zero():
    df = grid(21, [{0: "Brand : 4179 - GLAD2GLOW"},
                   {0: "1220001", 5: "12", 10: "1", 11: "145         "},
                   {0: "1220083", 5: "-", 10: "-", 11: "-"},
                   {0: "Total Brand : 4179 - GLAD2GLOW", 20: 123}],
              {0: "Item\n Code", 11: "Available\n Qty"})
    rec, n, iss = run("BMS_STOCK", "SRLO", df, 0)
    assert list(rec.qty) == [145, 0] and set(rec.branch) == {"SRLO"} and n == 2
    assert rec.qty.iloc[0] == 145        # Available Qty, not Allocated(12) / On Delivery(1)
    assert "DASH_AS_ZERO" in set(iss.code)


def test_bms_period_found():
    df = grid(21, [{4: "Period", 7: ":", 9: "31-10-2026"}, {0: "1220001", 11: 5}], {0: "Item Code"})
    assert find_stock_period(df, "BMS_STOCK") == dt.date(2026, 10, 31)


def test_bgk_text_qty_parsed_and_foreign_unit_is_critical():
    df = grid(6, [{}, {0: "G2G-20901", 4: "268 PCS"}, {0: "G2G-1", 4: "5 CRT"}],
              {0: "KODE BARANG", 2: "QTY / CRT", 4: "STOCK"})
    rec, n, iss = run("BGK_STOCK", "BGK", df, 0)
    assert rec.iloc[0].qty == 268 and not bool(rec.iloc[1].is_valid)
    assert "UNSUPPORTED_UNIT" in set(iss.code)


def test_blt_stock_and_update_date():
    df = grid(9, [{1: "STOCK UPDATE :", 3: dt.datetime(2026, 11, 7, 9, 51)},
                  {1: 1, 2: "G2G-2883", 8: 103}], None)
    df.loc[2] = [None, "No", "KODE", "NAMA BARANG", "ISI", None, None, None, "QTY (PCS)"]
    df = df.iloc[[0, 2, 1]].reset_index(drop=True)
    rec, n, _ = run("BLT_STOCK", "BLT", df, 1)
    assert rec.iloc[0].sku_raw == "G2G-2883" and rec.iloc[0].qty == 103
    assert rec.iloc[0].stock_period == dt.date(2026, 11, 7)


def test_zero_stock_rows_are_kept():
    df = grid(15, [{0: "377029", 6: 0, 14: "311000GS - 311000 - GUDANG BAIK"}], {0: "ItemID"})
    rec, _, _ = run("SJP_STOCK", "SJP", df, 0, sheet="PLB1")
    assert len(rec) == 1 and rec.iloc[0].qty == 0
