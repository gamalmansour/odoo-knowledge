# `TRUNCATE account_move CASCADE` Wipes `res_company` and the Entire Odoo Database

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | database / orm                             |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)              |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `database`, `postgresql`, `truncate`, `cascade`, `account_move`, `res_company`, `account_opening_move_id`, `master-data`, `purge`

---

## Problem

When cloning a production/staging database to create a **Master-Data-Only sandbox** (`createdb -T prod_db test_db`) and running `TRUNCATE TABLE account_move, sale_order, stock_picking, ... RESTART IDENTITY CASCADE;` to clear transactional records, **every master data table in the database (`res_company`, `res_partner`, `account_account`, `product_template`, `stock_warehouse`, `res_users`) is wiped to 0 rows**.

## Root Cause

In PostgreSQL:
- `res_company` has a nullable foreign key column `account_opening_move_id` referencing `account_move(id) ON DELETE SET NULL`.
- Unlike `DELETE FROM account_move`, which respects `ON DELETE SET NULL` and simply sets `res_company.account_opening_move_id = NULL`, **`TRUNCATE TABLE account_move CASCADE` ignores `ON DELETE SET NULL` and truncates the referencing table (`res_company`)**.
- Once `res_company` is included in the `TRUNCATE ... CASCADE` chain, PostgreSQL recursively truncates every table in the database that has a `company_id REFERENCES res_company(id)` foreign key (`res_partner`, `account_account`, `account_journal`, `stock_warehouse`, `stock_location`, `product_template`, `res_users`, etc.).

## Solution ✅

1. **NEVER use `TRUNCATE ... CASCADE` to clear transactional tables in Odoo.**
2. First explicitly nullify `res_company.account_opening_move_id`:
   ```sql
   UPDATE res_company SET account_opening_move_id = NULL WHERE account_opening_move_id IS NOT NULL;
   ```
3. Use ordered `DELETE FROM "<table_name>";` statements inside savepoints (from child line tables to parent header tables). `DELETE FROM` strictly honors PostgreSQL foreign key actions (`ON DELETE CASCADE` on child lines, `ON DELETE SET NULL` on nullable pointers, and `ON DELETE RESTRICT` as a safety guard if a master table still references a row).

```python
cur.execute("UPDATE res_company SET account_opening_move_id = NULL WHERE account_opening_move_id IS NOT NULL;")
for tbl in TRANSACTIONAL_TABLES:
    cur.execute("SAVEPOINT sp_del;")
    try:
        cur.execute(f'DELETE FROM "{tbl}";')
        cur.execute("RELEASE SAVEPOINT sp_del;")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_del;")
```

## ⚠️ Pitfalls

- `TRUNCATE ... CASCADE` is a DDL-level table wipe in PostgreSQL: it operates on whole tables, not rows, so any table with ANY foreign key to a truncated table (even a nullable `ON DELETE SET NULL` column) is completely emptied.
- Do not reset `ir_sequence` rows that back master-data numbering (such as `res_partner_company_type.sequence_id` for Partner ID Codes) when resetting transactional document sequences (`number_next = 1`).

## Verification

```sql
SELECT
  (SELECT count(*) FROM res_company) AS companies,
  (SELECT count(*) FROM res_partner) AS partners,
  (SELECT count(*) FROM account_account) AS accounts,
  (SELECT count(*) FROM product_template) AS products,
  (SELECT count(*) FROM stock_warehouse) AS warehouses,
  (SELECT count(*) FROM sale_order) AS sale_orders,
  (SELECT count(*) FROM account_move) AS moves,
  (SELECT count(*) FROM stock_picking) AS pickings,
  (SELECT count(*) FROM stock_quant) AS quants;
```
Expected: All master counts match the source database (`> 0`), and all transactional counts are `0`.
