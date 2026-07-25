# upgrade.odoo.com dumps ship WITHOUT the filestore — audit before promising attachments

## Metadata
- **Category:** Setup / Migrations
- **Severity:** 🔴 Critical
- **Odoo Versions:** All
- **Tags:** `filestore`, `ir.attachment`, `upgrade.odoo.com`, `backup`, `migration`
- **Last Verified:** 2026-07-25
- **Author:** ENG/Gamal Mansour

## Problem ❌
A database restored from an upgrade.odoo.com result (or any SQL-only dump)
looks complete, but `ir_attachment` rows point at files that were never
delivered: invoices open, the PDF attachment 404s. On Solargy UAE the DB
referenced ~1,500 unique files while the filestore folder held 141 (16 MB
vs ~600 MB implied) — including 369 invoice PDFs.

## Solution ✅
Audit FIRST, before scoping any migration:
```sql
SELECT count(DISTINCT store_fname) FROM ir_attachment WHERE store_fname IS NOT NULL;
```
vs `find <data_dir>/filestore/<db> -type f | wc -l`, and compare
`sum(file_size)` with `du -sh`. If they diverge, the real files live only on
the ORIGINAL server (`~/.local/share/Odoo/filestore/<dbname>`) or inside a
full backup zip (its `filestore/` folder).

Recovery order:
1. Files are content-addressed by sha1 (`store_fname = ab/<sha1>`), so check
   OTHER local filestores for the same checksums — real recoveries happen
   (433 files recovered from the target DB's own filestore in our case).
2. Ship a manifest CSV (attachment id, model, name, store_fname) of what is
   still missing and have the client copy the original filestore — files
   just drop into place, **no DB change needed**.

## ⚠️ Pitfalls
- `db_datas` is NULL for filestore-backed attachments — you cannot rebuild
  the file from the DB.
- Don't migrate module-art attachments (payment.method icons, ir.ui.view
  assets…) into another DB — the target's own modules provide them.
