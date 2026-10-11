# A Stored Compute Replacing an onchange: required=True and default= Both Break It

| Field         | Value        |
|---------------|--------------|
| Category      | orm          |
| Odoo Versions | All          |
| Severity      | 🟡 Medium    |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `computed-fields`, `onchange`, `store`, `required`, `default`, `not-null`

---

## Problem

Converting a form-only `@api.onchange` into a stored compute (so automation, imports and
the API get the value too — here: material unit cost from the product) failed twice in a
row, in two different ways:

**Attempt 1 — keep `required=True`:**
```
psycopg2.errors.NotNullViolation: null value in column "unit_cost"
of relation "project_material_issue" violates not-null constraint
```

**Attempt 2 — add `default=0.0` to satisfy the constraint:**
```
AssertionError: 0.0 != 75.0 : created by automation or import, the cost must still be filled
```
Every line silently kept cost zero — the compute never ran at all.

## Root Cause

Two separate ORM behaviours collide with the innocent-looking field definition:

1. **`required=True` places a NOT NULL constraint on the column, and Odoo INSERTs the row
   before running stored computes.** At insert time the computed value does not exist yet,
   so the database rejects the row — the compute never gets its chance.

2. **A `default=` is treated as an explicitly provided value, and a compute is skipped for
   records whose field already has a value.** So the default doesn't just seed the insert,
   it *replaces* the computation permanently. `readonly=False` (user-editable compute)
   makes this worse: the default looks exactly like a manual entry the compute must respect.

A third, quieter trap sits inside the compute body itself: **reading the field being
computed** (`price = rec.unit_cost or 0.0`) re-enters the compute for a record that has no
value yet.

## Solution ✅

Drop **both** `required=True` and `default=`. The compute must simply always assign:

```python
# Deliberately NOT required: `required=True` puts a NOT NULL constraint on the column,
# and Odoo INSERTs the row before running computes, so the insert is rejected before
# the cost is ever calculated. Supplying a default instead is worse — Odoo treats a
# default as an explicit value and skips the compute entirely. The compute always
# assigns, so the field can never end up empty.
unit_cost = fields.Float(
    string='Unit Cost', compute='_compute_unit_cost', store=True, readonly=False,
    digits='Product Price')

@api.depends('product_id', 'uom_id')
def _compute_unit_cost(self):
    for rec in self:
        price = 0.0                      # always assign; never read rec.unit_cost here
        if rec.product_id:
            price = rec.product_id.standard_price
            uom = rec.uom_id or rec.product_id.uom_id
            if uom and uom != rec.product_id.uom_id:
                price = rec.product_id.uom_id._compute_price(price, uom)
        rec.unit_cost = price
```

If emptiness must be forbidden at the model level, enforce it with an `@api.constrains`
(which runs *after* computes) — not with the SQL constraint that `required=True` creates.

Keep the old onchange only for what genuinely belongs to the form (e.g. defaulting the
UoM), and note why the cost is no longer set there.

## ⚠️ Pitfalls

- **Redefining the field in an `_inherit` module does NOT reset its attributes.** Field
  redefinition *merges* with the base definition: unspecified attributes survive. Adding
  `compute=...` in an extension while the base says `required=True` quietly recreates the
  NOT NULL trap — the override must say `required=False` explicitly:
  ```python
  # construction_equipment extension over construction_project's required rate field
  rate = fields.Float(compute='_compute_rate', store=True, readonly=False, required=False)
  ```

- The "mandatory" star on the form can be kept without the SQL constraint via
  `required="1"` in the **view**, which is UI-level only.
- `readonly=False` computes are recomputed when dependencies change but respect manual
  writes; that is exactly right for a price the user may override — but it is also why a
  `default=` poisons them.
- The one-per-record loop must assign on **every** branch. A `continue` that skips
  assignment reproduces the NotNullViolation for that record.
- Test through plain `create()` — onchange-based behaviour can only be exercised through
  `Form()`, which is precisely how the zero-cost bug stayed invisible.

## Verification

```python
issue = env['project.material.issue'].create({
    'work_order_id': wo.id, 'product_id': cement.id, 'quantity': 10.0})
assert issue.unit_cost == 75.0      # no form, no onchange — still costed
issue.unit_cost = 82.5              # manual override survives
```

## References

- Related file: `backend/int-cast-on-config-parameter-crashes-on-human-input.md`
- Related file: `orm/analytic-plan-columns-hardcoded-account-id-finds-nothing.md`
