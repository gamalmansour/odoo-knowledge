# Changing company_dependent=True to Regular Field in Odoo 17+

**Tags:** `#orm`, `#database`, `#migration`, `#jsonb`, `#company_dependent`
**Odoo Versions:** 17.0, 18.0
**Category:** Database & Migrations
**Author:** ENG/Gamal Mansour
**Last Verified:** 2026-06-18

## 📝 Problem Description
When you change an existing field on a model from being `company_dependent=True` to a regular field (e.g., removing `company_dependent=True` to improve performance for Raw SQL updates), Odoo will **NOT** automatically cast or drop the column in the PostgreSQL database.

In Odoo 17+, `company_dependent` fields are stored natively on the table as a `jsonb` column (mapping company IDs to values). If you change it to a `fields.Boolean` in Python, Odoo's ORM schema update mechanism doesn't know how to safely cast a `jsonb` column into a `boolean`.

As a result, any raw SQL operations like:
```sql
UPDATE account_move SET is_sampled_audit = False WHERE id IN %s
```
will crash with a PostgreSQL DatatypeMismatch error:
`psycopg2.errors.DatatypeMismatch: column is_sampled_audit is of type jsonb but expression is of type boolean`

## ✅ Solution
You must manually drop the column (or cast it via a migration script) in the database before the python code can interact with it as a normal data type.

If the data inside can be discarded (e.g., a temporary flag like `is_sampled_audit`), simply drop and recreate the column using raw PostgreSQL commands:

```bash
# Connect to your database
psql -d blue_ocean

# Drop the old jsonb column
ALTER TABLE account_move DROP COLUMN IF EXISTS is_sampled_audit;

# Recreate it as the correct type (e.g., boolean)
ALTER TABLE account_move ADD COLUMN is_sampled_audit boolean DEFAULT false;
```

Alternatively, if you must preserve data, you need to write a pre-init or post-init migration hook in your module to parse the `jsonb` structure and populate the new column correctly before dropping the old one.

## ⚠️ Pitfalls
- **Don't ignore the migration!** Just running Odoo with `-u module_name` will not throw a visible error during upgrade, but the app will crash at runtime when the column is queried or updated using raw SQL or even the ORM in some contexts.
- Always check the PostgreSQL schema directly (`\d table_name`) when changing major field properties like `company_dependent`, `translate`, or `store`.
