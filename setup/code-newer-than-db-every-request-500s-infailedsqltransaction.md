# Code On Disk Newer Than The Database → Every Request 500s, And The Traceback Names The Wrong Error

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `upgrade`, `UndefinedColumn`, `InFailedSqlTransaction`, `psycopg2`, `debugging`, `red-herring`, `deployment`, `handover`

---

## Problem

> The server starts fine. Then **every single request returns 500** — including
> `/favicon.ico` — and the traceback in the log points at QWeb rendering the error page:

```
File "odoo/addons/base/models/ir_ui_view.py", line 1191, in _fetch_template_views
    views = IrUiView.search_fetch(domain, field_names, order=...)
psycopg2.errors.InFailedSqlTransaction: current transaction is aborted,
commands ignored until end of transaction block

INFO werkzeug: "GET /favicon.ico HTTP/1.1" 500 -
```

Reading that traceback sends you hunting through `ir.qweb`, `http_routing` and the
Studio QWeb override — **none of which are the problem**.

## Root Cause

Two separate things, and the second hides the first.

**1. The real failure.** New Python declares fields the database does not have yet,
because the module was updated on disk but `-u` was never run:

```
psycopg2.errors.UndefinedColumn: column res_company.solargy_gratuity_tier_years does not exist
```

Odoo builds its SELECT from the **registry** (the Python field definitions), not from
the table. Any read of that model therefore asks Postgres for a column that is not there.

**2. The red herring.** In Postgres, a failed statement poisons the whole transaction:
every subsequent command returns `InFailedSqlTransaction` until rollback. So the error
handler tries to render the 500 page, that render queries `ir.ui.view`, and *that*
raises `InFailedSqlTransaction`. **The traceback you are shown is the second failure,
not the first.**

This is why the symptom looks unrelated to what changed, and why it hits `/favicon.ico`
too: nothing can touch the database at all.

## Solution ✅

**Diagnose:** confirm the version gap before touching anything.

```sql
-- module version in the DB vs the manifest on disk
SELECT name, state, latest_version FROM ir_module_module WHERE name = 'my_module';

-- do the new columns actually exist?
SELECT count(*) FROM information_schema.columns
 WHERE table_name = 'res_company' AND column_name LIKE 'my_prefix%';

-- and any new table
SELECT to_regclass('public.my_new_model');
```

**Fix:** stop the server (it holds the database), run the upgrade, restart.

```bash
./odoo-bin -c my.conf -d my_db -u my_module --stop-after-init
```

## ⚠️ Pitfalls

- 🔴 **Never debug the `InFailedSqlTransaction` traceback.** Scroll UP in the log to the
  **first** `psycopg2.errors.*` of the request — usually `UndefinedColumn`,
  `UndefinedTable` or `NotNullViolation`. Everything after it is noise.
- **Every request fails, not just the affected screen.** The registry loads the field for
  every read of that model, and `res.company` / `res.users` are read on every request. A
  new field on a widely-read model takes the whole database down until `-u` runs.
- **The server starting successfully proves nothing.** The registry loads from Python; the
  mismatch only surfaces on the first query.
- **This is the standard failure of a "leave the code on disk, someone else upgrades"
  handover.** Whoever delivers the code must state the exact `-u` command, and whoever
  pulls it must run it before starting the server. A module that only changed Python
  logic needs no upgrade; a module that added a **field or a model** always does.
- **Say what the upgrade changes.** If the migration script moves data (settings copied
  onto companies, stale rows cleared), the person running `-u` is making a data change —
  they need to know that before they press enter, not after.
- **Check `latest_version`, not the manifest**, to know what the DB believes it has —
  migrations only run when the manifest version is HIGHER than `latest_version`.

## Verification

```bash
./odoo-bin -c my.conf -d my_db -u my_module --stop-after-init
```

```sql
SELECT latest_version FROM ir_module_module WHERE name = 'my_module';   -- == the manifest
SELECT count(*) FROM information_schema.columns
 WHERE table_name = 'res_company' AND column_name LIKE 'my_prefix%';    -- == expected
```

Then load any page: a database that comes back at all is fixed, because the failure was
total, not partial.

## Related

- `setup/manifest-assets-change-needs-server-restart.md` — the other "the code is newer than what is running" trap
- `upgrade/foreign-key-violation-ondelete-restrict.md` — when the upgrade itself is what fails
