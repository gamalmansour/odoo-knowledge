# Odoo Silently Auto-Creates a Missing `-d` Database — Masking a Wrong db_port/Cluster

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `postgres`, `db_port`, `upgrade`, `-u`, `migrations`, `debugging`

---

## Problem

> You run `odoo-bin -d mydb -u my_module --stop-after-init`, it exits 0 with no errors —
> but the module's `latest_version` never changes, migrations never run, and your psql
> queries say the new column doesn't exist. Nothing failed, yet nothing happened.

## Root Cause

Two things combine:

1. **Odoo auto-initializes a missing database.** If the `-d` database does not exist on
   the cluster Odoo connects to, Odoo quietly creates it and installs `base` — no error,
   no warning. The log shows `loading 1 modules... → updating modules list` (the
   signature of a fresh init, not an upgrade).
2. **Your `psql` and your Odoo config may talk to different Postgres clusters.** Plain
   `psql`/`createdb` use port 5432 by default, while the Odoo conf may say
   `db_port = 5433` (or a different host/user). You clone/inspect a DB on one cluster
   while Odoo upgrades a freshly-created empty one on the other.

## Solution ✅

- Always read the **startup banner** of the Odoo log — it prints the truth:
  ```
  INFO ? odoo: database: odoo@localhost:5433
  ```
  Compare that against where your `psql` is looking (`psql -p 5433 -U odoo -h localhost`).
- When verifying an upgrade, check `latest_version` **on the same cluster Odoo used**:
  ```sql
  SELECT latest_version FROM ir_module_module WHERE name = 'my_module';
  ```
- A fresh-init log signature (`loading 1 modules` + `updating modules list` + a small
  module count) on a DB you believed was populated = you're on the wrong cluster.

## ⚠️ Pitfalls

- `createdb -T prod_db clone_db` clones on the **psql** cluster; the subsequent
  `odoo-bin -d clone_db` may auto-create an empty `clone_db` on the **conf** cluster.
  Override explicitly: `--db_port=5432 --db_user=<owner>` if the data lives there.
- Exit code 0 from `--stop-after-init` proves nothing about the upgrade having touched
  your data — verify a migrated column/value directly with SQL.
- Leftover auto-created empty DBs pollute the other cluster; drop them after debugging.

## Versions

Behavior verified on Odoo 19.0; the auto-create behavior exists in all supported versions.
