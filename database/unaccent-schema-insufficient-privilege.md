# InsufficientPrivilege: permission denied for schema unaccent_schema

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | database                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-30                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `database`, `unaccent`, `unaccent_schema`, `permissions`, `insufficient-privilege`, `psycopg2`, `assets`, `account_move`

---

## Problem

When loading web assets or deleting attachments (or updating models like `account.move` with unaccented fields), Odoo crashes with a 500 error:

```
psycopg2.errors.InsufficientPrivilege: permission denied for schema unaccent_schema
LINE 2:                 SELECT unaccent_schema.unaccent('unaccent_sc...
                               ^
QUERY:  
                SELECT unaccent_schema.unaccent('unaccent_schema.unaccent', $1)
CONTEXT:  SQL function "unaccent" during inlining
SQL statement "UPDATE ONLY "public"."account_move" SET "extract_attachment_id" = NULL WHERE $1 OPERATOR(pg_catalog.=) "extract_attachment_id""
```

## Root Cause

Production dumps from Odoo.sh / Debian / Ubuntu create `unaccent` inside a dedicated schema:
```sql
CREATE SCHEMA unaccent_schema;
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA unaccent_schema;
CREATE FUNCTION public.unaccent(text) RETURNS text AS ...;
```

When restored by an OS user (e.g., `gamal` or `postgres`), `unaccent_schema` and the underlying C functions are owned by that user with no default `USAGE` grants to the local Odoo database user (`odoo`). When PostgreSQL attempts to inline `public.unaccent(text)`, it checks permissions on `unaccent_schema`. If `odoo` lacks `SUPERUSER` or `USAGE` on `unaccent_schema`, it aborts with `InsufficientPrivilege`.

## Solution ✅

1. Make the local dev `odoo` user a `SUPERUSER`:
```sql
ALTER USER odoo WITH SUPERUSER;
```

2. Grant ownership and full permissions on `unaccent_schema` and its functions:
```sql
ALTER SCHEMA unaccent_schema OWNER TO odoo;
GRANT ALL ON SCHEMA unaccent_schema TO odoo;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA unaccent_schema TO odoo;
ALTER SCHEMA public OWNER TO odoo;
GRANT ALL ON SCHEMA public TO odoo;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO odoo;
```

3. Reassign function ownership in `public` and `unaccent_schema`:
```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT oid::regprocedure as func_sig 
        FROM pg_proc 
        WHERE pronamespace IN (SELECT oid FROM pg_namespace WHERE nspname IN ('public', 'unaccent_schema'))
    ) LOOP
        EXECUTE 'ALTER FUNCTION ' || r.func_sig || ' OWNER TO odoo';
    END LOOP;
END $$;
```

## ⚠️ Pitfalls

- The error often triggers indirectly during `assetsbundle._unlink_attachments()` when Odoo regenerates JS/CSS bundles. The traceback points to `binary.py` or `assetsbundle.py`, but the actual root cause is database triggers on referencing tables (`account_move.extract_attachment_id`) calling `unaccent()`.
- On local dev machines, always grant `SUPERUSER` to the `odoo` role to prevent subtle permission traps with extensions.

## Verification

Test the function directly as the `odoo` user:
```bash
psql -U odoo -d <db_name> -c "SELECT public.unaccent('Hélène');"
# Expected: Helene
```
Then refresh `/web/login?db=<db_name>` — the asset bundles (`.min.js` and `.min.css`) must return HTTP 200 instead of HTTP 500.
