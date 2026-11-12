import datetime as dt
import io
import os

import pandas as pd
import pytest
from openpyxl import load_workbook

from config.settings import SALES_OUTPUT_COLUMNS, STOCK_OUTPUT_COLUMNS
from services.compilation_service import FileInput, apply_mapping, compile_files, compute_stats
from services.export_service import (BlockedByCriticalErrors, combined_workbook, sales_output, sales_workbook,
                                     stock_output, stock_workbook)
from tests.helpers import RUN

SAMPLES = os.environ.get("DSSC_SAMPLES", "/mnt/user-data/uploads")
have = os.path.isdir(SAMPLES) and any(f.endswith((".xls", ".xlsx")) for f in os.listdir(SAMPLES))
pytestmark = pytest.mark.skipif(not have, reason="sample files not available")

MAP = pd.DataFrame([["SJP", "376201", "G2G-1442", "approved", "", ""]],
                   columns=["scope", "original_sku", "sku_fix", "status", "note", "updated_at"])


@pytest.fixture(scope="module")
def res():
    files = [FileInput(f, open(os.path.join(SAMPLES, f), "rb").read())
             for f in sorted(os.listdir(SAMPLES)) if f.endswith((".xls", ".xlsx")) and f != "Book2.xlsx"]
    return compile_files(files, run_date=RUN), files


def test_all_sample_files_detected_without_failures(res):
    r, files = res
    assert r.failed_files == []
    det = r.detections
    assert set(det[det.status == "Detected"].file_name) == {f.name for f in files}


def test_not_current_month_notification_for_stale_stock(res):
    r, _ = res
    nm = r.issues[r.issues.code == "NOT_CURRENT_MONTH"]
    assert set(nm.file) == {"BGO_Stock_1.xls", "BGO_Stock_2.xls"}
    assert (r.stock.source_file.str.startswith("BGO")).sum() > 0     # still processed


def test_bgk_rows_without_invoice_included_and_flagged(res):
    r, _ = res
    bgk = r.sales[(r.sales.distributor == "BGK") & (r.sales.invoice_no == "")]
    assert len(bgk) == 23 and bgk.is_valid.all()
    assert (r.issues.code == "MISSING_INVOICE").sum() == 23


def test_bgk_zero_qty_rows_kept_with_warning(res):
    r, _ = res
    assert (r.issues.code == "ZERO_QTY").sum() == 5


def test_export_exact_columns_dates_and_text_ids(res):
    r, _ = res
    s, st = sales_output(r), stock_output(r)
    assert list(s.columns) == SALES_OUTPUT_COLUMNS and list(st.columns) == STOCK_OUTPUT_COLUMNS
    wb = load_workbook(io.BytesIO(combined_workbook(r)))
    assert wb.sheetnames == ["Sales Summary", "Stock Summary"]
    ws = wb["Sales Summary"]
    assert [c.value for c in ws[1]] == SALES_OUTPUT_COLUMNS
    assert ws["E2"].number_format == "DD/MM/YYYY" and isinstance(ws["E2"].value, dt.datetime)
    assert ws["D2"].number_format == "@" and isinstance(ws["D2"].value, str)
    assert ws.max_row == len(s) + 1


def test_mapping_reapply_changes_only_sku_fix_without_reupload(res):
    r, _ = res
    before = len(r.sales)
    r2 = apply_mapping(r, MAP)
    hit = r2.sales[r2.sales.sku_raw == "376201"]
    assert len(r2.sales) == before and (hit.sku_fix == "G2G-1442").all() and (hit.mapping_status == "MAPPED").all()
    miss = r2.sales[r2.sales.mapping_status == "UNMAPPED"]
    assert (miss.sku_fix == miss.sku_raw).all()                       # as-is, but visibly flagged
    assert (r2.issues.code == "UNMAPPED_SKU").any()


def test_critical_rows_block_export_until_excluded(res):
    r, _ = res
    r.sales.loc[0, "is_valid"] = False
    try:
        with pytest.raises(BlockedByCriticalErrors):
            sales_output(r)
        assert len(sales_output(r, exclude_invalid=True)) == len(r.sales) - 1
    finally:
        r.sales.loc[0, "is_valid"] = True


def test_duplicate_file_is_skipped_and_reported():
    p = os.path.join(SAMPLES, "BLT_Sales.xlsx")
    data = open(p, "rb").read()
    r = compile_files([FileInput("BLT_Sales.xlsx", data), FileInput("BLT_Sales_copy.xlsx", data)], run_date=RUN)
    assert len(r.sales) == 77 and "DUPLICATE_FILE" in set(r.issues.code)


def test_same_data_in_two_different_files_not_double_counted(tmp_path):
    p = os.path.join(SAMPLES, "BLT_Sales.xlsx")
    df = pd.read_excel(p, header=None, dtype=object)
    buf = io.BytesIO()
    df.to_excel(buf, header=False, index=False)          # different bytes, same data
    r = compile_files([FileInput("BLT_Sales.xlsx", open(p, "rb").read()), FileInput("BLT_again.xlsx", buf.getvalue())],
                      run_date=RUN)
    assert len(r.sales) == 77
    assert "DUPLICATE_SOURCE" in set(r.issues.code)
