# Multi-Instance Cookie Conflict: cids '2-1-3' ValueError in web_studio (Odoo 17 vs 18)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 17, 18                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `cookie`, `multi-instance`, `localhost`, `cids`, `web_studio`, `odoo18`, `odoo17`, `valueerror`

---

## Problem

When loading the Odoo 17 web client (`/web`), the page crashes with HTTP 500:

```
  File "enterprise/web_studio/models/ir_ui_menu.py", line 31, in load_menus
    cids = [int(cid) for cid in cids.split(',')]
ValueError: invalid literal for int() with base 10: '2-1-3'
```

## Root Cause

1. Browsers share all cookies across different ports on the same host domain (`localhost`).
2. In **Odoo 18**, the multi-company selection cookie (`cids`) changed its separator format from comma (`,`) to hyphen (`-`) via `CIDS_SEPARATOR = "-"` in `company_service.js`. For example, selecting companies 2, 1, and 3 produces `cids="2-1-3"`.
3. In **Odoo 17**, `web_studio` (`ir_ui_menu.py:31`) naively splits `cids` by comma only:
   ```python
   cids = [int(cid) for cid in cids.split(',')]
   ```
4. If a developer uses Odoo 18 on `localhost` and then opens Odoo 17 on `localhost:8017`, the browser transmits `cids=2-1-3`. Splitting on `,` leaves `'2-1-3'`, causing `int('2-1-3')` to crash.

## Solution ✅

### 1. Immediate Workaround (Clear Cookie)
- Open Browser DevTools (`F12`) → **Application** → **Cookies** → `localhost` → Delete the `cids` cookie.
- Or open Odoo in an Incognito / Private browsing window.

### 2. Isolation (Host Separation)
Never run multiple Odoo versions on the exact same host string.
- Access Odoo 17 via: `http://127.0.0.1:8017`
- Access Odoo 18 via: `http://localhost:8069`
The browser isolates cookie jars between IP addresses (`127.0.0.1`) and hostnames (`localhost`).

### 3. Defensive Code Patch (enterprise/web_studio/models/ir_ui_menu.py)
Make the cookie parsing resilient to both separators and invalid values:

```python
# Replace:
# cids = [int(cid) for cid in cids.split(',')]

# With:
separator = '-' if '-' in cids else ','
cids = [int(cid) for cid in cids.split(separator) if cid.isdigit()]
```

## Verification
Send a request with `cids=2-1-3`:
```bash
curl -b "cids=2-1-3" http://localhost:8017/web
```
Should render without throwing `ValueError`.
