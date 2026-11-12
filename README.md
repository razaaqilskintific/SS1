# Daily Sales & Stock Compiler

Konsolidasi harian Sales dan Stock dari distributor (SJP, JMB, MBO/BGO, SRLO, BGK, BLT).

**Status:** mesin pemrosesan + antarmuka Streamlit (7 halaman) selesai dan teruji (64+ tes otomatis).
Belum dilakukan: deploy ke Streamlit Community Cloud dan uji dengan sheet mapping Google langsung (butuh internet).

## Output (kolom persis)
- Sales: `DST BRANCH | SALES ID | CUST ID | CUST NAME | INVOICE DATE | NO. INVOICE | SKU Fix | QTY`
- Stock: `QTY | BRANCH | SKU_Fix`
- Tanggal selalu berupa tanggal Excel asli berformat `DD/MM/YYYY`. ID dan nomor invoice selalu teks.

## Aturan utama
| Area | Aturan |
|---|---|
| Tanggal | Teks dibaca day-first (dd/mm/yyyy). Angka serial Excel dan datetime dikonversi. Tidak ada lagi tukar bulan-hari. |
| SJP Sales | QTY = kolom M (Pcs). Cabang dari 6 digit awal `Nama Gudang` (311000 PLM, 311001 BTA, 311002 LHT, 311003 PRB). |
| JMB/BGO(MBO)/SRLO Sales | QTY = kolom `CTN` (berisi qty satuan). Distributor dari awalan kode customer (JMB/BGO/SLR), bukan dari nomor di nama file. |
| BGK Sales | QTY = `QtyNonBonusPcs`. |
| BLT Sales | QTY = kolom `Qty`; tanggal teks dd/mm/yyyy. |
| Stock BMS | QTY = `Available Qty` (bukan Allocated / On Delivery). `-` dibaca 0. |
| Stock BGK | `268 PCS` -> 268. Satuan selain PCS = error kritis. |
| Stock BLT | Hanya sheet `G2G` (`config/distributors.py: BLT_STOCK_SHEETS`). |
| Bukan bulan berjalan | Tetap diproses, diberi peringatan `NOT_CURRENT_MONTH`. |
| Qty 0, tanpa nomor invoice, tanggal setelah hari proses | Tetap diikutkan, diberi peringatan. |
| Qty negatif | Retur; diikutkan, info. |
| Error kritis (tanggal/qty tidak valid, SKU kosong, cabang tidak valid) | Ekspor diblokir kecuali pengguna memilih mengeluarkan baris tersebut. |

## Mapping SKU (satu tabel panjang, mudah dirawat)
Kolom: `Scope | Kode Asli | SKU Fix | Status | Catatan`. Scope: `*`, `SJP`, `BMS` (JMB+MBO+SRLO), `BGK`, `BLT`, atau distributor spesifik.
Urutan: distributor -> family -> `*` -> kode sudah berupa SKU Fix yang dikenal -> `UNMAPPED`.
Kode tidak ter-mapping tidak pernah ditebak: kebijakan default `passthrough_flagged` memakai kode distributor apa adanya
di kolom SKU Fix **dan selalu menandainya** (`UNMAPPED_SKU`). Set `DSSC_UNMAPPED_POLICY=block` untuk memblokir ekspor.
Saran (awalan G, fuzzy) hanya usulan dan tidak pernah diterapkan otomatis. Ubah mapping -> `apply_mapping()` memproses ulang
tanpa upload ulang.

## Penyimpanan
SQLite (`data/mapping.db`) untuk lokal. Disk Streamlit Community Cloud TIDAK permanen: untuk produksi implementasikan
`MappingStore` yang sama (load/upsert/replace_all/snapshot/restore) di atas Postgres/Supabase. Backup = `export_xlsx()`.

## Menjalankan tes
```bash
pip install -r requirements.txt
python -m pytest -q tests                      # tes integrasi memakai file contoh jika ada (DSSC_SAMPLES=/path)
python scripts/run_samples.py /path/to/files   # ringkasan deteksi + validasi
python scripts/reconcile_extraction.py /path   # rekonsiliasi ekstraksi vs data mentah
```

## Menjalankan aplikasi
```bash
pip install -r requirements.txt
streamlit run app.py
```
Halaman: Dashboard (app.py) -> Upload Files -> Sales Compilation -> Stock Compilation -> SKU Mapping -> Validation Report -> Download Center.

## Mapping dari Google Sheets (disarankan)
1. Sheet mapping dibagikan "Siapa saja yang memiliki link -> Pelihat". Kolom: `Kode DST` + `Kode HO` (atau `Kode Asli` + `SKU Fix`).
   Baris judul di atas header boleh ada. Tanpa kolom `Scope` semua baris berlaku untuk semua distributor.
2. Isi link di Streamlit Cloud: *App settings -> Secrets*:
   ```toml
   MAPPING_SHEET_URL = "https://docs.google.com/spreadsheets/d/XXXX/edit?gid=0#gid=0"
   ```
   (atau variabel lingkungan `MAPPING_SHEET_URL`; atau tempel di halaman SKU Mapping untuk sesi itu saja).
3. Aplikasi membaca sheet otomatis (cache 5 menit). Tombol *Muat ulang sekarang* memaksa baca ulang.
4. Aturan yang ditambahkan lewat aplikasi disimpan di lapisan lokal dan MENANG atas Google Sheet. Di Streamlit Cloud lapisan
   lokal hilang saat aplikasi di-restart, jadi tempel aturan penting kembali ke Google Sheet (unduh CSV dari tab *Belum ter-mapping*).

## Deploy ke Streamlit Community Cloud
1. Push repo ke GitHub (file Excel distributor TIDAK ikut karena `.gitignore`).
2. https://share.streamlit.io -> Create app -> pilih repo & branch, Main file path: `app.py`.
3. Advanced settings -> Secrets: isi `MAPPING_SHEET_URL`.
