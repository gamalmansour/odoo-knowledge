# QWeb t-esc Incomplete `%` Format Crashes Portal Page (500) — and Stale DB Arch Hides the Fix

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `qweb`, `t-esc`, `portal`, `500`, `format-string`, `arch_db`, `stale-view`, `dev-mode`

---

## Problem

A portal page (e.g. `/my/targets/<id>` target detail) returns **HTTP 500** for portal users. The server traceback shows:

```
ValueError: incomplete format
Template: sale_target.portal_target_detail
Element: <span ... t-esc="'%.1f%' % line.achievement_pct"/>
```

Confusingly, the XML file on disk already contains the CORRECT code (`'%.1f%%'`), yet the page still crashes.

## Root Cause

Two stacked causes:

1. **The format string bug itself:** in Python, a trailing single `%` in a format string is invalid — `'%.1f%' % 5.0` raises `ValueError: incomplete format`. To print a literal percent sign you must escape it as `%%`: `'%.1f%%' % 5.0` → `'5.0%'`. Inside a QWeb `t-esc` this raises at render time, i.e. only when a record actually reaches that element (here: a target WITH product carton lines), so the template installs and upgrades green.

2. **Stale `arch_db`:** the fix (`%` → `%%`) was applied to the XML file on disk, but the module was never upgraded (`-u`) on the affected database afterwards. QWeb renders `ir.ui.view.arch_db` from the DB, not the file — so the broken single-`%` version kept serving. In Odoo 19 `arch_db` is JSONB per language (`en_US`, `ar_001`, …) and ALL language values keep the stale broken string.

**Why it "works on my machine":** with `dev = all` (which includes `dev=xml`), views are read directly from the source file, so the developer sees the fixed page locally while every server without dev mode (client test/production) still renders the broken DB arch and 500s.

## Solution ✅

1. Keep the correct escape on disk:

```xml
<span t-esc="'%.1f%%' % line.achievement_pct"/>
```

2. Upgrade the module on the affected database so the fixed arch is rewritten to `arch_db` (all languages re-synced):

```bash
python odoo-bin -c custom.conf -d <db_name> -u sale_target --stop-after-init
```

3. Verify against the DB directly (works per language key):

```sql
SELECT key, lang.lang_key, (arch_db->>lang.lang_key ~ '%\.1f%''') AS has_broken_pct
FROM ir_ui_view, LATERAL jsonb_object_keys(arch_db) AS lang(lang_key)
WHERE key = 'sale_target.portal_target_detail';
```

All rows must return `f` after the upgrade.

## ⚠️ Pitfalls

- **`-u` on the wrong cluster:** on machines with two PostgreSQL clusters (e.g. psql default 5432 vs Odoo conf 5433), Odoo silently auto-creates a missing DB and "upgrades" the wrong one. Always check the startup log line `database: user@host:port` (see [odoo-silent-db-autocreate-masks-wrong-cluster](../setup/odoo-silent-db-autocreate-masks-wrong-cluster.md)).
- **Don't trust local rendering as proof:** `dev=xml` masks stale-arch problems entirely. Reproduce with the DB arch (shell render or a server without dev mode) before declaring a template bug fixed.
- **The crash is data-dependent:** the element only evaluates when the surrounding `t-if`/`t-foreach` produces rows, so smoke-testing with an empty record shows a green page while real users 500.
- **Shell reproduction recipe (Odoo 19):** `MockRequest` moved to `odoo.addons.http_routing.tests.common`, and in `odoo shell` (no HTTP server) `HttpCase.http_port()` raises `AttributeError` — patch it first: `HttpCase.http_port = classmethod(lambda cls: None)`, then `with MockRequest(env(user=rep.id)): env['ir.qweb']._render('module.template', values)` gives the real portal traceback without needing portal credentials.

## Verification

- Rendered `sale_target.portal_targets` (list) and `sale_target.portal_target_detail` as the actual portal salesperson via `MockRequest` in `odoo shell`: list OK, detail reproduced the exact `ValueError: incomplete format` at the carton badge.
- Confirmed disk file had `%%` while `arch_db` (both `en_US` and `ar_001`) still had the single `%` → stale arch, fixed by `-u`.

## References

- Related file: [views/portal_templates.xml](file:///Users/gamal/odoo/odoo19.0/custom/sale_target/views/portal_templates.xml)
- Related KB: [odoo-silent-db-autocreate-masks-wrong-cluster](../setup/odoo-silent-db-autocreate-masks-wrong-cluster.md), [db-artifacts-newer-than-code-blocks-module-install](../upgrade/db-artifacts-newer-than-code-blocks-module-install.md)
