# Fix Duplicate Key Violation on data_merge_rule During Base Upgrade

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `base`, `data_cleaning`, `data_merge`, `unique-constraint`, `ir_model_data`, `psycopg2`

---

## Problem

When performing an upgrade on `base` or the Enterprise module `data_cleaning`, the process crashes with a PostgreSQL unique constraint violation:

```text
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "data_merge_rule_uniq_model_id_field_id"
DETAIL:  Key (model_id, field_id)=(1, 1008) already exists.

odoo.tools.convert.ParseError: while parsing /enterprise/data_cleaning/data/data_cleaning_data.xml:44, somewhere inside
<record model="data_merge.rule" id="data_merge_field_res_partner_name">
    <field name="model_id" ref="data_merge_model_res_partner"/>
    <field name="field_id" ref="base.field_res_partner__name"/>
    <field name="match_mode">exact</field>
</record>
```

## Root Cause

In `data_merge.rule`, there is a unique SQL constraint `data_merge_rule_uniq_model_id_field_id` across `(model_id, field_id)`.

When an administrator edits deduplication rules in the UI (Data Cleaning > Configuration > Deduplication Rules) or deletes default rules, Odoo's `unlink()` removes the corresponding `ir_model_data` entries (`data_merge_field_res_partner_name`, `data_merge_field_res_partner_vat`). If the rules were later recreated manually in the UI, they exist in `data_merge_rule` with new IDs, but with **no XML ID mapping** in `ir_model_data`.

During any future module upgrade of `base` or `data_cleaning`, Odoo re-imports `data_cleaning_data.xml`. Because the XML ID is missing from `ir_model_data`, Odoo attempts `_load_records_create()`, which triggers an `INSERT` statement into PostgreSQL. PostgreSQL rejects the insert because the combination of `(model_id, field_id)` already exists.

## Solution ✅

Identify the existing IDs in `data_merge_rule` and re-link them to `ir_model_data`.

### Step 1: Identify Existing Rule IDs
```sql
SELECT r.id, r.model_id, m.name AS model_name, r.field_id, f.name AS field_name
FROM data_merge_rule r
JOIN data_merge_model m ON m.id = r.model_id
JOIN ir_model_fields f ON f.id = r.field_id
WHERE m.res_model_name = 'res.partner' AND f.name IN ('name', 'vat');
```

### Step 2: Restore the XML ID Mappings
Insert the missing references into `ir_model_data` pointing to the matching existing records:

```sql
INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
VALUES 
('data_cleaning', 'data_merge_field_res_partner_name', 'data_merge.rule', <ID_OF_NAME_RULE>, false),
('data_cleaning', 'data_merge_field_res_partner_vat', 'data_merge.rule', <ID_OF_VAT_RULE>, false)
ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
```

### Step 3: Run Upgrade
Run the upgrade again via CLI or web UI:
```bash
odoo-bin -c odoo.conf -u data_cleaning,base --stop-after-init
```

Odoo will now find the existing records via `ir_model_data` and execute an `UPDATE` (`write()`) instead of `create()`.

## ⚠️ Pitfalls

- **Do NOT delete the rows from `data_merge_rule` directly:** They might be referenced in deduplication workflows or configured specifically by the business.
- **Do NOT alter or drop the unique constraint:** Dropping `data_merge_rule_uniq_model_id_field_id` will allow duplicate rules for the same field, causing unpredictable deduplication behavior and merge algorithm conflicts.

## Verification

Run CLI upgrade:
```bash
odoo-bin -c custom.conf -u base --stop-after-init
```
Expected output:
```text
INFO pure_integrated odoo.modules.loading: Module data_cleaning loaded in ...
INFO pure_integrated odoo.modules.loading: Modules loaded.
```

---
