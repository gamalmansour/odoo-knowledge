# Inconsistent 'store' or 'compute_sudo' for Computed Fields Sharing One Compute Method

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-06-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `compute_sudo`, `registry`, `undefined-column`

---

## Problem

When upgrading or installing an Odoo module, a computed field defined as `store=True` is missing from the database (resulting in `psycopg2.errors.UndefinedColumn: column <model>.<field> does not exist` when accessing views or executing queries), accompanied by the following registry UserWarnings on startup:

```
UserWarning: <model>: inconsistent 'store' for computed fields, accessing <non_stored_fields> may recompute and update <stored_fields>. Use distinct compute methods for stored and non-stored fields.
UserWarning: <model>: inconsistent 'compute_sudo' for computed fields. Either set 'compute_sudo' to the same value on all those fields, or use distinct compute methods for sudoed and non-sudoed fields.
```

## Root Cause

Odoo's registry compilation parses all fields computed by a single method. If a single compute method is shared between some fields that are `store=True` and others that are `store=False`, or fields with different `compute_sudo` defaults:
1. Odoo triggers a consistency check.
2. The database manager skips creating the columns for the stored fields in PostgreSQL because the registry marks the dependency evaluation as inconsistent.
3. However, since the field is marked `store=True` in Python, Odoo's web read/search controller includes the column in the generated SQL queries, causing PostgreSQL to raise an `UndefinedColumn` database error.

## Solution ✅

Split the computed fields into distinct compute methods: one method for `store=True` fields and another method for `store=False` fields.

### Example:
**Before (Inconsistent):**
```python
    stored_amount = fields.Float(compute='_compute_values', store=True)
    non_stored_ids = fields.Many2many('res.partner', compute='_compute_values', store=False)

    @api.depends(...)
    def _compute_values(self):
        for rec in self:
            rec.stored_amount = 100.0
            rec.non_stored_ids = self.env['res.partner'].search([])
```

**After (Consistent):**
```python
    stored_amount = fields.Float(compute='_compute_stored_values', store=True)
    non_stored_ids = fields.Many2many('res.partner', compute='_compute_non_stored_values', store=False)

    @api.depends(...)
    def _compute_stored_values(self):
        for rec in self:
            rec.stored_amount = 100.0

    @api.depends(...)
    def _compute_non_stored_values(self):
        for rec in self:
            rec.non_stored_ids = self.env['res.partner'].search([])
```

## ⚠️ Pitfalls

- **Performance (N+1 Queries):** If both methods perform similar query lookups, make sure they are written efficiently (e.g. batch search and map) to avoid repeating database queries.
- **Always Upgrade:** Always upgrade the module with `-u <module_name>` after making python changes to computed fields to force Odoo to recreate database columns.

## Verification

Run Odoo upgrade:
```bash
python3 odoo-bin -c odoo.conf -u your_module -d your_db --stop-after-init
```
Verify that the `added column '<field>' of type ...` log appears and no `inconsistent 'store'` warnings are raised.
