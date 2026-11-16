"""Entry point + menu definition.   Run with:  streamlit run app.py

To rename a menu item, change `title=`; to change its icon, change `icon=` (emoji or
":material/<name>:", see https://fonts.google.com/icons). Section headers are the dictionary keys.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import streamlit as st

from config import settings
from ui import components as ui, state

st.set_page_config(page_title=settings.APP_NAME, page_icon=settings.PAGE_ICON, layout="wide")
state.init()
ui.chrome()

MENU = {
    "": [st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True)],
    "Proses harian": [
        st.Page("views/upload_files.py", title="Upload Files", icon=":material/upload_file:"),
        st.Page("views/sales_compilation.py", title="Sales Compilation", icon=":material/receipt_long:"),
        st.Page("views/stock_compilation.py", title="Stock Compilation", icon=":material/inventory_2:"),
    ],
    "Pengaturan & hasil": [
        st.Page("views/sku_mapping.py", title="SKU Mapping", icon=":material/link:"),
        st.Page("views/validation_report.py", title="Validation Report", icon=":material/fact_check:"),
        st.Page("views/download_center.py", title="Download Center", icon=":material/download:"),
    ],
}
st.navigation(MENU).run()
