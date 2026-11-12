import pandas as pd
from processors.mapping_processor import (apply_mapping_to_records, build_lookup, resolve_sku, suggest_for_unmapped)
from services.mapping_service import MappingStore, read_mapping_file


def mp(rows):
    return pd.DataFrame(rows, columns=["scope", "original_sku", "sku_fix", "status", "note", "updated_at"])


MAP = mp([["SJP", "376201", "G2G-1442", "approved", "", ""],
          ["BMS", "1220114", "G2G-276", "approved", "", ""],
          ["BLT", "GBSR111002", "BSR111002", "approved", "", ""],
          ["*", "BSR111002", "BSR111002", "approved", "", ""],
          ["SJP", "999", "X-1", "suggested", "", ""]])


def test_family_scope_and_no_cross_distributor_collision():
    lk, ho, _ = build_lookup(MAP)
    assert resolve_sku("SJP", "376201", lk, ho)[:2] == ("G2G-1442", "MAPPED")
    assert resolve_sku("BGK", "376201", lk, ho)[1] == "UNMAPPED"      # SJP code must not resolve for BGK
    assert resolve_sku("JMB", "1220114", lk, ho)[0] == "G2G-276"
    assert resolve_sku("SJP", "1220114", lk, ho)[1] == "UNMAPPED"


def test_leading_zeros_and_case_and_numeric_keys():
    lk, ho, _ = build_lookup(mp([["BMS", "00123", "A-1", "approved", "", ""]]))
    assert resolve_sku("JMB", "00123", lk, ho)[0] == "A-1"
    assert resolve_sku("JMB", "123", lk, ho)[1] == "UNMAPPED"          # 123 != 00123


def test_already_ho_code_is_verified_not_guessed():
    lk, ho, _ = build_lookup(MAP)
    assert resolve_sku("BGK", "BSR111002", lk, ho)[1] == "MAPPED"      # explicit '*' row wins over identity check
    s = resolve_sku("BGK", "G2G-1442", lk, ho)
    assert s[0] == "G2G-1442" and s[1] == "VALID_HO_CODE"


def test_suggested_rows_are_not_applied_and_unmapped_never_invented():
    lk, ho, _ = build_lookup(MAP)
    assert resolve_sku("SJP", "999", lk, ho)[1] == "UNMAPPED"


def test_passthrough_flags_but_keeps_code_and_block_leaves_empty():
    rec = pd.DataFrame({"distributor": ["SJP", "SJP"], "sku_raw": ["376201", "376386"]})
    a = apply_mapping_to_records(rec, MAP, passthrough=True)
    assert list(a.sku_fix) == ["G2G-1442", "376386"] and list(a.mapping_status) == ["MAPPED", "UNMAPPED"]
    b = apply_mapping_to_records(rec, MAP, passthrough=False)
    assert list(b.sku_fix) == ["G2G-1442", ""]


def test_conflicting_mapping_reported():
    _, _, conf = build_lookup(mp([["BMS", "1", "A", "approved", "", ""], ["BMS", "1", "B", "approved", "", ""]]))
    assert len(conf) == 1


def test_suggestions_prefix_g_and_fuzzy_only_suggest():
    un = pd.DataFrame({"distributor": ["BLT", "BLT"], "sku_raw": ["GNJM103001", "ZZZ"]})
    m = mp([["BMS", "1", "NJM103001", "approved", "", ""]])
    s = suggest_for_unmapped(un, m)
    assert list(s.suggested_sku_fix) == ["NJM103001"] and list(s.rule) == ["buang awalan G"]


def test_store_roundtrip_version_snapshot_restore(tmp_path):
    st = MappingStore(str(tmp_path / "m.db"))
    st.upsert(MAP.iloc[:3])
    v1 = st.version()["version"]
    snap = st.snapshot("x")
    st.upsert(mp([["SJP", "1", "Z", "approved", "", ""]]))
    assert st.version()["version"] > v1 and len(st.load()) == 4
    st.restore(snap)
    assert len(st.load()) == 3
    assert isinstance(st.export_xlsx(), bytes)


def test_read_mapping_file_aliases_and_problems():
    csv = b"Distributor,Kode DST,Kode HO,Catatan\nSJP,376201,G2G-1442,a\nSJP,376201,G2G-9999,b\nXX,1,2,c\nSJP,,3,d\n"
    df, problems = read_mapping_file("m.csv", csv)
    assert any("Konflik" in p for p in problems) and any("tidak dikenal" in p for p in problems) \
        and any("kosong" in p for p in problems)
    assert not df.empty


def _book2_like():
    import io
    rows = [["Master Product BMS", None, None], ["Kode DST", "Nama DST", "Kode HO"],
            [1220001, "G18 CENTELLA", "G2G-18"], [1220001, "G18 CENTELLA", "G2G-18"],
            [376201, None, "G2G-1442"], ["GBSR111002", None, "BSR111002"], [None, None, None]]
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, header=False, index=False)
    return buf.getvalue()


def test_read_legacy_style_file_with_title_row_and_no_scope():
    df, problems = read_mapping_file("Book2.xlsx", _book2_like())
    assert len(df) == 3 and set(df.scope) == {"*"}
    assert list(df.original_sku) == ["1220001", "376201", "GBSR111002"]
    assert any(p.startswith("Info: 1 baris duplikat") for p in problems)
    assert not any("Konflik" in p for p in problems)


def test_gsheet_url_conversion_and_merge():
    from services.mapping_source import gsheet_csv_url, merge_mappings
    u = gsheet_csv_url("https://docs.google.com/spreadsheets/d/ABC_123/edit?gid=42#gid=42")
    assert u == "https://docs.google.com/spreadsheets/d/ABC_123/export?format=csv&gid=42"
    base = mp([["*", "1", "A", "approved", "", ""], ["*", "2", "B", "approved", "", ""]])
    local = mp([["*", "1", "A2", "approved", "", ""], ["*", "2", "", "rejected", "", ""]])
    m = merge_mappings(base, local)
    lk, _, _ = build_lookup(m)
    assert lk[("*", "1")] == "A2" and ("*", "2") not in lk
