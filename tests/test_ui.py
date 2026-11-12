"""Smoke tests: every page renders with real sample data and without exceptions."""
import os
import datetime as dt

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from config import settings
from services.compilation_service import FileInput, apply_mapping, compile_files
from services.mapping_service import read_mapping_file

SAMPLES = os.environ.get("DSSC_SAMPLES", "/mnt/user-data/uploads")
MAPFILE = os.path.join(SAMPLES, "Book2.xlsx")
have = os.path.exists(os.path.join(SAMPLES, "SJP_Sales.xlsx"))
pytestmark = pytest.mark.skipif(not have, reason="sample files not available")

PAGES = ["app.py", "pages/1_Upload_Files.py", "pages/2_Sales_Compilation.py", "pages/3_Stock_Compilation.py",
         "pages/4_SKU_Mapping.py", "pages/5_Validation_Report.py", "pages/6_Download_Center.py"]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    settings.DB_PATH = str(tmp_path_factory.mktemp("db") / "m.db")
    from ui import state
    state.get_store.clear()
    if os.path.exists(MAPFILE):
        df, _ = read_mapping_file("Book2.xlsx", open(MAPFILE, "rb").read())
        state.get_store().upsert(df, note="test")
    files = [FileInput(f, open(os.path.join(SAMPLES, f), "rb").read()) for f in sorted(os.listdir(SAMPLES))
             if f.endswith((".xls", ".xlsx")) and f != "Book2.xlsx"]
    res = compile_files(files, run_date=dt.date(2026, 11, 12))
    return apply_mapping(res, state.get_store().load())


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_page(path, result=None):
    at = AppTest.from_file(os.path.join(ROOT, path), default_timeout=120)
    if result is not None:
        at.session_state["result"] = result
        at.session_state["compiled_at"] = dt.datetime.now()
    return at.run()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_data(page, result):
    at = run_page(page, result)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("page", PAGES[2:3] + PAGES[3:4] + PAGES[5:])
def test_data_pages_show_hint_without_data(page):
    at = run_page(page)
    assert not at.exception
    assert any("Belum ada data" in i.value for i in at.info)


def test_dashboard_kpis_and_warnings(result):
    at = run_page("app.py", result)
    labels = [m.label for m in at.metric]
    assert {"Total file diunggah", "Total record Sales", "Total record Stock", "Sheet berhasil diproses",
            "File/sheet gagal", "SKU belum ter-mapping"} <= set(labels)
    assert any("bukan bulan berjalan" in w.value for w in at.warning)


def test_download_center_has_three_exact_files(result):
    at = run_page("pages/6_Download_Center.py", result)
    assert not at.exception
    from streamlit.testing.v1.element_tree import ElementTree  # noqa: F401
    labels = [b.label for b in at.get("download_button")]
    assert labels == ["Sales Summary.xlsx", "Stock Summary.xlsx", "Combined Report.xlsx"]


def test_download_blocked_when_critical_rows(result):
    import copy
    r = copy.deepcopy(result)
    r.sales.loc[0, "is_valid"] = False
    at = run_page("pages/6_Download_Center.py", r)
    assert any("diblokir" in e.value for e in at.error)
    assert not at.get("download_button")
