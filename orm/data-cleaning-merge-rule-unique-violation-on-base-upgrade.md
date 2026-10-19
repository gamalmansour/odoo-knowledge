# `UniqueViolation: data_merge_rule_uniq_model_id_field_id` During `-u base` or `data_cleaning` Upgrade

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / upgrade                              |
| Odoo Versions | 16, 17, 18, 19 (Enterprise)                |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `data_cleaning`, `data_merge.rule`, `UniqueViolation`, `data_merge_rule_uniq_model_id_field_id`, `ir_model_data`, `noupdate`, `base`, `upgrade`

---

## Problem

When upgrading `base` (or `data_cleaning`) from the UI or CLI, the upgrade crashes while parsing `enterprise/data_cleaning/data/data_cleaning_data.xml`:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "data_merge_rule_uniq_model_id_field_id"
DETAIL:  Key (model_id, field_id)=(1, 1008) already exists.
...
odoo.tools.convert.ParseError: while parsing enterprise/data_cleaning/data/data_cleaning_data.xml:44, somewhere inside
<record model="data_merge.rule" id="data_merge_field_res_partner_name">
    <field name="model_id" ref="data_merge_model_res_partner"/>
    <field name="field_id" ref="base.field_res_partner__name"/>
    <field name="match_mode">exact</field>
</record>
```

## Root Cause

1. `enterprise/data_cleaning/data/data_cleaning_data.xml` seeds default deduplication rules (`data_merge.rule`) for `res.partner` (`name`, `vat`, `email`, `ref`) inside `<data noupdate="1">`.
2. If an administrator previously deleted the default `name` or `vat` rule in the **Data Cleaning → Configuration → Deduplication** UI, Odoo also deleted its corresponding `ir_model_data` XML ID (`data_cleaning.data_merge_field_res_partner_name` / `data_cleaning.data_merge_field_res_partner_vat`).
3. If the administrator subsequently re-added `name` or `vat` on the `Contact` (`res.partner`) deduplication model via the UI, the new row in `data_merge_rule` has **no `ir_model_data` entry**.
4. During `-u base` (which cascades to `data_cleaning`), `<data noupdate="1">` only skips records whose XML ID still exists in `ir_model_data`. Because the XML ID is missing, Odoo attempts to `INSERT` a new `data_merge_rule` for `(model_id, field_id)`, colliding with the UI-created rule on the unique constraint `data_merge_rule_uniq_model_id_field_id`.

## Solution ✅

Re-link the existing `data_merge_rule` rows to their canonical `ir_model_data` XML IDs with `noupdate = true`:

```sql
INSERT INTO ir_model_data (name, module, model, res_id, noupdate, create_uid, create_date, write_uid, write_date)
SELECT 'data_merge_field_res_partner_name', 'data_cleaning', 'data_merge.rule', r.id, true, 1, NOW(), 1, NOW()
FROM data_merge_rule r
JOIN ir_model_fields f ON f.id = r.field_id
WHERE r.model_id = (SELECT res_id FROM ir_model_data WHERE module='data_cleaning' AND name='data_merge_model_res_partner')
  AND f.model = 'res.partner' AND f.name = 'name'
ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id, noupdate = true;

INSERT INTO ir_model_data (name, module, model, res_id, noupdate, create_uid, create_date, write_uid, write_date)
SELECT 'data_merge_field_res_partner_vat', 'data_cleaning', 'data_merge.rule', r.id, true, 1, NOW(), 1, NOW()
FROM data_merge_rule r
JOIN ir_model_fields f ON f.id = r.field_id
WHERE r.model_id = (SELECT res_id FROM ir_model_data WHERE module='data_cleaning' AND name='data_merge_model_res_partner')
  AND f.model = 'res.partner' AND f.name = 'vat'
ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id, noupdate = true;
```

## ⚠️ Pitfalls

- Deleting the rule from `data_merge_rule` instead of re-linking `ir_model_data` would cause Odoo to recreate the default rule (including `email` and `ref`), overwriting the admin's custom `match_mode` configuration on subsequent upgrades if unlinked again. Re-linking `ir_model_data` with `noupdate = true` preserves the existing rule ID and skips re-insertion on every future `-u base`.

## Verification

```bash
./odoo-bin -c custom.conf -d <db_name> --no-http --stop-after-init -u data_cleaning
# Expected: exits 0 with no UniqueViolation
```
