# "module X: not installable, skipped" + "Some modules are not loaded" — Leftover Module in DB

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `modules`, `not-installable`, `test_performance`, `odoo-sh`, `database`, `cleanup`

---

## Problem

> On every server start / deploy (locally or on Odoo.sh):

```
WARNING server module test_performance: not installable, skipped
ERROR   server Some modules are not loaded, some dependencies or manifest may be missing: ['test_performance']
```

## Root Cause

The database has the module registered as `installed` in `ir_module_module`, but the
module's source is absent from the current addons path (or `installable: False`).
Typical causes: a `--test-enable` run installed an Odoo test module (e.g.
`test_performance`) into a DB that was later kept; or the DB was moved between
environments whose checkouts differ. The DB carries the module's `ir.model` records,
metadata and tables forever, and complains on every registry load.

## Solution ✅

Purge the remnants with SQL (safe for pure test modules — verify the module holds no
business data first). Adapt model/table names to the module:

```sql
BEGIN;
DELETE FROM ir_model WHERE id IN (SELECT res_id FROM ir_model_data
  WHERE module='test_performance' AND model='ir.model');
DELETE FROM ir_model_data WHERE module='test_performance';
UPDATE ir_module_module SET state='uninstalled' WHERE name='test_performance';
DROP TABLE IF EXISTS test_performance_base, test_performance_tag,
  test_performance_eggs, test_performance_bacon, test_performance_simple_minded,
  test_performance_mozzarella, test_performance_line CASCADE;
COMMIT;
```

List the module's models first to know which tables to drop:

```sql
SELECT model FROM ir_model WHERE id IN (SELECT res_id FROM ir_model_data
  WHERE module='test_performance' AND model='ir.model');
```

On **Odoo.sh**: branch → Shell tab → `psql` → paste the block → `\q` → `odoosh-restart`.
If staging rebuilds from production, clean production too or the warning returns on
every rebuild.

## ⚠️ Pitfalls

- For a module that owned real business data, do NOT use this shortcut — reinstate the
  source and uninstall properly from the Apps menu instead.
- Never run `--test-enable` against a database you intend to keep; use throwaway DBs.
- `DROP TABLE ... CASCADE` also drops relation tables (m2m) — expected for test modules.

## Versions

Verified on Odoo 19 (local + Odoo.sh).
