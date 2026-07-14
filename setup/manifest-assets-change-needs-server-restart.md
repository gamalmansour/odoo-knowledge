# Manifest `assets` change needs a full server restart — `-u` alone won't serve the new file

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All (verified 19)                          |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-14                                 |
| Author        | Gamal Mansour                              |

**Tags:** `setup`, `assets`, `manifest`, `dev-mode`, `bundle`, `frontend`, `restart`

---

## Problem

> You add a **new** JS/CSS file to `__manifest__.py` → `'assets'` (e.g. a new
> `web.assets_frontend` entry), run `-u <module>`, hard-refresh the browser —
> and the feature does nothing. The new file is simply **not in the served
> bundle**. No error anywhere.

```js
// in the browser console on a frontend/portal page — returns false
const u = [...document.querySelectorAll('script[src]')]
  .map(s => s.src).find(s => s.includes('assets_frontend_lazy'));
fetch(u).then(r => r.text()).then(t => console.log(t.includes('my-signature-string')));
```

This bites hardest when a long-running `dev = all` server is up: you *expect*
the auto-reloader to pick the change up, and it doesn't.

## Root Cause

- Each module's manifest is parsed into **memory at server start**. The asset
  bundles (`web.assets_frontend`, etc.) are built from that in-memory manifest.
- Manifest-declared assets are **not** stored as `ir.asset` records — so
  querying `ir_asset` for the new path returns nothing even when everything is
  correct. (`ir.asset` only holds assets declared as `<record model="ir.asset">`.)
- Running `-u <module>` in a **separate process** reads the manifest fresh and
  upgrades the DB, but the long-running server keeps its **stale** in-memory
  manifest and keeps serving the old bundle.
- The `dev = all` (werkzeug) reloader only watches **imported** Python modules.
  `__manifest__.py` is read via `ast`/eval, **not imported**, so editing it does
  **not** trigger a restart.

Net: the new asset file never enters the served bundle until the **server
process itself restarts**.

## Solution ✅

> Restart the Odoo server process after any change to the `assets` list (same
> goes for `depends` / `data` lists) in `__manifest__.py`.

```bash
# 1. stop the running server (graceful)
kill -TERM <pid>          # find it: lsof -iTCP:8019 -sTCP:LISTEN -n -P

# 2. relaunch with the SAME command it was started with
.venv/bin/python odoo-bin -c odoo19_dev.conf

# 3. (optional) also pass -u <module> to refresh views/models/security in the DB
#    — needed for data changes, but NOT sufficient on its own for assets.
```

## ⚠️ Pitfalls

- Editing the **content** of an already-registered asset file (JS/CSS) *is*
  picked up in dev mode without a restart (bundles rebuild per request). It is
  only the manifest **list** (adding/removing a file) that needs the restart.
- Do **not** rely on the `ir_asset` table to confirm a manifest asset is
  registered — it is empty for manifest-declared assets by design.
- Hard-refresh the browser after the restart: the bundle hash changes
  (`/web/assets/OLD/... → /web/assets/NEW/...`), but a cached HTML page may still
  point at the old hash.

## Verification

```js
// after restart, on any frontend page — bundle hash changes and now returns true
const u = [...document.querySelectorAll('script[src]')]
  .map(s => s.src).find(s => s.includes('assets_frontend_lazy'));
fetch(u).then(r => r.text()).then(t => console.log(t.includes('my-signature-string')));
```

## References

- Related file: `setup/odoo-silent-db-autocreate-masks-wrong-cluster.md`
- Related file: `setup/data-addons-write-permissions.md`
