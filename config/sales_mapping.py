"""Sales column positions (0-based) per source layout.

Positions are authoritative (headers may be renamed by distributors); `expected` holds the
header text normalised (lower-case, no whitespace) used for detection and layout checks.
"""
SALES_PROFILES = {
    "SJP_SALES": {
        "family": "SJP",
        "expected": {0: "outlet", 1: "namaoutlet", 3: "salesid", 5: "tglfaktur", 6: "nofaktur",
                     7: "pcode", 9: "unitid", 10: "qty", 11: "unitid", 12: "qty",
                     26: "suppliername", 27: "namagudang"},
        # QTY = column M (the Pcs quantity). Branch is derived from Nama Gudang (column AB).
        "cols": {"sales_id": 3, "cust_id": 0, "cust_name": 1, "invoice_date": 5,
                 "invoice_no": 6, "sku": 7, "qty": 12},
        "gudang_col": 27,
    },
    "BMS_SALES": {   # Jambi, Bungo (BGO), Sarolangun
        "family": "BMS",
        "expected": {0: "customercode", 1: "customername", 2: "salesmancode", 3: "invoicedate",
                     4: "invoiceno", 5: "itemcode", 7: "principalcode", 8: "ctn"},
        # The column named CTN holds unit quantity (price per unit x CTN = gross), so it is used as QTY.
        "cols": {"sales_id": 2, "cust_id": 0, "cust_name": 1, "invoice_date": 3,
                 "invoice_no": 4, "sku": 5, "qty": 8},
        "customer_col": 0,
    },
    "BGK_SALES": {
        "family": "BGK",
        "expected": {0: "tanggal", 1: "kodesupplier", 3: "kodesalesman", 5: "nofaktur",
                     6: "kodecustomer", 7: "namacustomer", 9: "kodebarang", 11: "qtynonbonuspcs"},
        # QtyNonBonusPcs only. Never QtyPcs / QtyCrt without business confirmation.
        "cols": {"sales_id": 3, "cust_id": 6, "cust_name": 7, "invoice_date": 0,
                 "invoice_no": 5, "sku": 9, "qty": 11},
    },
    "BLT_SALES": {
        "family": "BLT",
        "expected": {0: "no.faktur", 1: "tgl.faktur", 5: "kodebarang", 7: "kodesalesman",
                     9: "kodelangganan", 10: "namalangganan", 15: "isidus", 16: "qty"},
        "cols": {"sales_id": 7, "cust_id": 9, "cust_name": 10, "invoice_date": 1,
                 "invoice_no": 0, "sku": 5, "qty": 16},
    },
}
