import datetime as dt
import pandas as pd
from processors.validation import IssueLog

RUN = dt.date(2026, 11, 12)


def grid(width, rows, header=None):
    """Raw sheet (header=None layout). rows: list of {col_index: value}."""
    data = []
    if header is not None:
        r = [None] * width
        for k, v in header.items():
            r[k] = v
        data.append(r)
    for row in rows:
        r = [None] * width
        for k, v in row.items():
            r[k] = v
        data.append(r)
    return pd.DataFrame(data, dtype=object)


def new_log():
    return IssueLog()
