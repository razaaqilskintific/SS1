"""Golden pairs copied from the legacy workbook's Sales sheet (column H -> column K, rows 2-100)."""
import os
import pytest
from processors.mapping_processor import build_lookup, resolve_sku
from services.mapping_service import read_mapping_file

BOOK2 = os.environ.get("DSSC_BOOK2", "/mnt/user-data/uploads/Book2.xlsx")
GOLDEN = {"376201": "G2G-1442", "376222": "G2G-43", "376224": "G2G-45", "376226": "G2G-51", "376229": "G2G-72",
          "376289": "G2G-276", "376362": "G2G-42", "376363": "G2G-71", "376196": "G2G-131", "376270": "G2G-251",
          "376193": "G2G-05", "376195": "G2G-110", "376207": "G2G-231", "376208": "G2G-232", "376209": "G2G-233",
          "376214": "G2G-29", "376237": "G2G-83", "376374": "G2G-272", "376302": "G2G-262", "376347": "G2G-322",
          "377028": "BSR111002", "377030": "BSR112002", "377032": "BSR113002", "377041": "NJM103001",
          "377043": "NJM105001", "377046": "NYZ109", "377047": "NYZ107", "376192": "G2G-04"}


@pytest.mark.skipif(not os.path.exists(BOOK2), reason="Book2.xlsx not available")
def test_engine_matches_legacy_sku_fix_for_golden_pairs():
    df, _ = read_mapping_file("Book2.xlsx", open(BOOK2, "rb").read())
    lk, ho, _ = build_lookup(df)
    wrong = {k: (v, resolve_sku("SJP", k, lk, ho)[0]) for k, v in GOLDEN.items() if resolve_sku("SJP", k, lk, ho)[0] != v}
    assert not wrong, wrong


@pytest.mark.skipif(not os.path.exists(BOOK2), reason="Book2.xlsx not available")
def test_codes_the_legacy_workbook_passed_through_are_unmapped_here_and_flagged():
    """376386/376387 came out of the legacy workbook unchanged (silent fallback). Here they are explicit UNMAPPED."""
    df, _ = read_mapping_file("Book2.xlsx", open(BOOK2, "rb").read())
    lk, ho, _ = build_lookup(df)
    for k in ("376386", "376387"):
        assert resolve_sku("SJP", k, lk, ho)[1] == "UNMAPPED"
