# Database Not Showing in Odoo Selector Due to datdba Owner Mismatch

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | database                                   |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)              |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-30                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `database`, `list_dbs`, `db_user`, `datdba`, `owner`, `selector`, `postgresql`, `missing-db`

---

## Problem

After creating or restoring a database in PostgreSQL via `createdb` or SQL dump, the database exists in PostgreSQL (`psql -l`) and the configured user can connect to it, but it **does not appear in the Odoo Database Selector** (`/web/database/selector`) or in `odoo.service.db.list_dbs()`. No error is logged.

## Root Cause

In Odoo (`odoo/service/db.py`), `list_dbs()` queries PostgreSQL using:

```sql
SELECT datname FROM pg_database 
 WHERE datdba = (SELECT usesysid FROM pg_user WHERE usename = current_user) 
   AND NOT datistemplate 
   AND datallowconn 
   AND datname NOT IN %s 
 ORDER BY datname;
```

Notice `datdba = (SELECT usesysid FROM pg_user WHERE usename = current_user)`.
Odoo explicitly filters databases where the database owner (`datdba`) matches the PostgreSQL user configured in Odoo (`db_user`, e.g. `odoo`).

If the database was created by the OS superuser (e.g. `createdb -U gamal <dbname>`), its owner is `gamal`. Even if privileges were granted via `GRANT ALL PRIVILEGES ON DATABASE <dbname> TO odoo`, `datdba` remains `gamal`. Consequently, `list_dbs()` filters it out silently.

## Solution ✅

Change the database owner to the Odoo PostgreSQL user (`db_user`), and reassign all table/sequence/view ownerships:

```bash
# 1. Transfer database ownership
psql -U postgres -c "ALTER DATABASE <dbname> OWNER TO odoo;"

# 2. Reassign all tables, sequences, and views in the public schema to odoo
psql -U postgres -d <dbname> -c "
DO \$\$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(r.tablename) || ' OWNER TO odoo';
    END LOOP;
    FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
        EXECUTE 'ALTER SEQUENCE ' || quote_ident(r.sequence_name) || ' OWNER TO odoo';
    END LOOP;
    FOR r IN (SELECT table_name FROM information_schema.views WHERE table_schema = 'public') LOOP
        EXECUTE 'ALTER VIEW ' || quote_ident(r.table_name) || ' OWNER TO odoo';
    END LOOP;
END \$\$;
"
```

## ⚠️ Pitfalls

- Running `GRANT ALL PRIVILEGES ON DATABASE <dbname> TO odoo;` is **NOT sufficient** — Odoo checks `datdba` (ownership), not access privileges.
- Check `db_filter` in your `.conf` file: even if the owner is correct, an active `db_filter` (e.g. `db_filter = .*17.*`) will hide any database whose name does not match the regex.

## Verification

Test with Odoo's internal helper using your config file:

```bash
python3 -c "
from odoo.tools import config
config.parse_config(['-c', 'odoo17_dev.conf'])
from odoo.service.db import list_dbs
print('Database present:', '<dbname>' in list_dbs())
"
```

Expected: `Database present: True`
And navigate to `http://localhost:8017/web/database/selector` to verify it appears in the dropdown.
