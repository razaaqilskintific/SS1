"""Stock column positions (0-based) per source layout."""
STOCK_PROFILES = {
    "SJP_STOCK": {   # one sheet per branch; branch comes from the Gudang column
        "family": "SJP",
        "expected": {0: "itemid", 1: "description", 6: "endingbalance(qty)",
                     11: "principle", 14: "gudang"},
        "cols": {"sku": 0, "qty": 6, "gudang": 14},
    },
    "BMS_STOCK": {   # 'BRANCH STOCK REPORT' (Jambi, Bungo, Sarolangun); QTY = Available Qty
        "family": "BMS",
        "expected": {0: "itemcode", 1: "itemname", 5: "allocatedqty",
                     10: "ondeliveryqty", 11: "availableqty"},
        "cols": {"sku": 0, "qty": 11},
    },
    "BGK_STOCK": {   # "S A L D O  G U D A N G"; STOCK is text such as "268 PCS"
        "family": "BGK",
        "expected": {0: "kodebarang", 1: "namabarang", 2: "qty/crt", 4: "stock"},
        "cols": {"sku": 0, "qty": 4},
    },
    "BLT_STOCK": {
        "family": "BLT",
        "expected": {1: "no", 2: "kode", 3: "namabarang", 4: "isi", 8: "qty(pcs)"},
        "cols": {"sku": 2, "qty": 8},
    },
}
