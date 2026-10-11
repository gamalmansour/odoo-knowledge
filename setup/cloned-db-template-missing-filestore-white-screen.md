# Cloned Database Missing Filestore Causes White Screen (500 FileNotFoundError on Assets)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (16, 17, 18, 19)                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `database`, `cloning`, `createdb`, `filestore`, `white-screen`, `assets`, `500`, `FileNotFoundError`

---

## Problem

After cloning an existing Odoo database directly via PostgreSQL (`createdb -T template_db new_db`), navigating to `/web` or `/odoo` renders a **completely blank / white screen** in the browser. 

In the Odoo server console/logs, multiple HTTP 500 errors appear:
```
FileNotFoundError: [Errno 2] No such file or directory: '<data_dir>/filestore/<new_db>/...'
"GET /web/assets/.../web.assets_web.min.css HTTP/1.1" 500
"GET /web/assets/.../web.assets_web.min.js HTTP/1.1" 500
```

## Root Cause

1. `createdb -T` only duplicates the PostgreSQL database catalog and tables.
2. In Odoo, binary attachments and compiled asset bundles (`web.assets_web.min.js`, `web.assets_web.min.css`) have metadata rows in PostgreSQL (`ir.attachment`), but the actual binary payload is stored on the filesystem under `<data_dir>/filestore/<database_name>/`.
3. Because the PostgreSQL table was cloned, `ir.attachment` records in `new_db` point to file hashes (`store_fname`) that do not exist inside `<data_dir>/filestore/<new_db>/`.
4. When Werkzeug attempts to serve the JS/CSS bundles, `ir_binary` tries to `os.stat(stream.path)` and raises `FileNotFoundError`, returning HTTP 500. Without CSS/JS, the web client (OWL) fails to mount, resulting in a blank white screen.

## Solution ✅

### 1. Copy the Source Database Filestore

Immediately clone the source filestore directory to the new database name:

```bash
# If using custom data_dir:
cp -R "<data_dir>/filestore/<template_db>" "<data_dir>/filestore/<new_db>"

# If using default system location on macOS:
cp -R "~/Library/Application Support/Odoo/filestore/<template_db>" "~/Library/Application Support/Odoo/filestore/<new_db>"

# If using default system location on Linux:
cp -R "~/.local/share/Odoo/filestore/<template_db>" "~/.local/share/Odoo/filestore/<new_db>"
```

### 2. Force Asset Bundle Regeneration (Optional / Recommended)

If the template filestore was cleaned or incomplete, delete existing asset attachment records from the database so Odoo recompiles fresh ones:

```sql
DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
```
Or append `?debug=assets` to the URL to inspect which bundle fails.

## Verification

Send an HTTP `HEAD` or `GET` request to the asset URL:
```bash
curl -sI "http://localhost:8018/web/assets/.../web.assets_web.min.js"
```
Must return `HTTP/1.1 200 OK` with non-zero `Content-Length`.
