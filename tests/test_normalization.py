import datetime as dt
import pandas as pd
from utils.normalization import clean_text, text_id, to_date, to_number, parse_stock_qty, norm_key


def test_text_id_preserves_leading_zeros_and_float_ints():
    assert text_id("00123")[0] == "00123"
    assert text_id(78126039913.0)[0] == "78126039913"
    assert text_id(3110000062)[0] == "3110000062"
    assert text_id(None)[0] == ""


def test_scientific_notation_flagged():
    assert text_id("3.11E+09")[1] == "SCIENTIFIC_NOTATION"


def test_dates_all_representations_same_result():
    target = dt.date(2026, 11, 6)
    assert to_date(dt.datetime(2026, 11, 6))[0] == target
    assert to_date(pd.Timestamp("2026-11-06"))[0] == target
    assert to_date(46332)[0] == target                 # Excel serial (SJP mixed column)
    assert to_date("06/11/2026")[0] == target          # BLT text, day first
    assert to_date("06-11-2026")[0] == target
    assert to_date("2026-11-06")[0] == target


def test_date_is_day_first_never_month_first():
    assert to_date("02/11/2026")[0] == dt.date(2026, 11, 2)


def test_invalid_dates():
    assert to_date("abc")[0] is None
    assert to_date(12)[0] is None
    assert to_date(None)[1] == "MISSING_DATE"


def test_to_number():
    assert to_number(3)[0] == 3
    assert to_number("52         ")[0] == 52
    assert to_number("-")[1] == "DASH"
    assert to_number("abc")[0] is None
    assert to_number("1.234")[0] == 1234 and to_number("1.234")[1] == "AMBIGUOUS_FORMAT"
    assert to_number(-1)[0] == -1


def test_parse_stock_qty():
    assert parse_stock_qty("268 PCS") == (268, "PCS", None)
    assert parse_stock_qty("0 PCS")[0] == 0
    assert parse_stock_qty(103) == (103, "", None)
    assert parse_stock_qty("-") == (0, "", "DASH_AS_ZERO")
    assert parse_stock_qty("12 CRT")[1] == "CRT"
    assert parse_stock_qty("abc")[0] is None


def test_norm_key():
    assert norm_key(" g2g-02 ") == "G2G-02"
    assert norm_key(1220001.0) == "1220001"
