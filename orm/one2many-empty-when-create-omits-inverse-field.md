# One2many Table Renders Empty When Programmatic create() Omits Inverse Many2one Field

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All (15, 16, 17, 18, 19)                   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `one2many`, `many2one`, `create`, `write`, `approval`, `silent-ui-gap`, `foreign-key`

---

## Problem

After approving a record in a multi-step workflow (e.g., reaching final approval state `waiting_approval_4`), lines are supposed to be generated and displayed in a One2many notebook tab (e.g. `commission_line_ids`). However, the table in the UI remains completely empty even though no Python error is thrown.

Investigation in PostgreSQL reveals that the child records were indeed inserted into the target table, but their inverse relation column (e.g., `commission_ambassador_id`) is `NULL`.

## Root Cause

In a lifecycle trigger (like `write()` when transitioning to an approved state), programmatic calls to `self.env['child.model'].create({...})` omitted the inverse Many2one foreign key:

```python
# ❌ BUG: 'commission_ambassador_id' is missing
commission_lines.create({
    'sales_type': 'personal',
    'ambassador': rec.ambassador_id.id,
    'personal': rec.commission_amount,
    # commission_ambassador_id is omitted!
})
```

Because `One2many('child.model', 'commission_ambassador_id')` filters child records where `child.commission_ambassador_id == parent.id`, records with `NULL` inverse fields are orphaned and never shown in the parent's form view.

## Solution ✅

1. **Always pass the parent record ID** explicitly in the `create()` dictionary:
```python
# ✅ CORRECT: Pass inverse Many2one field
commission_lines.create({
    'sales_type': 'personal',
    'ambassador': rec.ambassador_id.id,
    'personal': rec.commission_amount,
    'commission_ambassador_id': rec.id,  # Link to parent
    'tcr_id': rec.tcr_id.id if rec.tcr_id else False,
})
```

2. **Ensure Downstream Hierarchy Methods Receive Parent ID:**
If delegating generation to a helper method (e.g. `tcr._create_commissions_if_not_exist()`), pass `rec.id` so all generated supervisor/agent lines also inherit the parent link when intended.

3. **Check for Existing Lines Before Create:**
Avoid creating duplicate child lines if the record is saved or processed again:
```python
existing = commission_lines.search([
    ('commission_ambassador_id', '=', rec.id),
    ('ambassador', '=', rec.ambassador_id.id),
], limit=1)
if not existing:
    commission_lines.create(...)
```

## ⚠️ Pitfalls

- **Context Default Trap:** If the parent record was opened from another model (e.g., TCR) with `context={'default_tcr_id': self.id}`, the child record might inherit `tcr_id` from the context, masking the fact that neither `tcr_id` nor `commission_ambassador_id` was explicitly passed.
- **Computed Amount Dependencies:** Ensure computed fields feeding the child lines (like `commission_amount = percentage * unit_price`) include all dependent factors in `@api.depends` (e.g. `unit_price`), otherwise child lines will be created with `0.0` amount.

## Verification

Query the database after approval:
```sql
SELECT id, commission_ambassador_id, personal FROM commission_lines WHERE commission_ambassador_id = <parent_id>;
```
The records should exist and have `commission_ambassador_id` populated, and appear immediately in the parent form view.
