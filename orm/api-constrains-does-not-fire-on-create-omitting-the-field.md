# `@api.constrains` for a "field must be set" Rule Does NOT Fire When create() Omits Every Trigger Field — Enforce at a Lifecycle Gate

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `constrains`, `create`, `validation`, `required`, `related-field`, `x2many`

---

## Problem

Relaxing a `required=True` field to conditionally-required (e.g. "required in strict mode, else at least one line") and enforcing it with `@api.constrains`:

```python
@api.constrains('boq_item_id', 'item_ids', 'cost_control_mode')
def _check_has_scope(self):
    for rec in self:
        if rec.cost_control_mode == 'strict' and not rec.boq_item_id:
            raise ValidationError(...)
        elif not rec.boq_item_id and not rec.item_ids:
            raise ValidationError(...)
```

`create({'project_id': ..., 'description': ...})` — omitting `boq_item_id` AND `item_ids` — **saves without raising.** The guard silently never runs, so the "must have scope" rule is not enforced on the exact case it exists for (an empty record).

## Root Cause

`@api.constrains` methods run during `_validate_fields`, which is called with the set of fields that were **actually written**. On create, a constrained field that is (a) absent from the create vals and (b) a related/computed field, or an x2many left empty, may not be in that set — so the constraint method is skipped. In this example none of the three triggers is reliably "written":

- `boq_item_id` — absent from vals (that is the bug being tested), default False.
- `item_ids` — an x2many not present in vals; empty o2m does not count as modified.
- `cost_control_mode` — a **related** field (computed), not in vals.

So the method has no trigger and never fires. (Constraints are reliable when at least one trigger field is genuinely in the vals — which is why the same pattern "works" in tests that always pass one of the fields.)

## Solution ✅

Do not use `@api.constrains` for "this record must have X" when X can be omitted. Enforce it at a **lifecycle gate** you call explicitly — `action_confirm` / `action_done` / a button — where the check always runs:

```python
def action_confirm(self):
    self._check_scope_ready()          # always runs
    self.write({'state': 'confirmed'})

def _check_scope_ready(self):
    for rec in self:
        if rec.cost_control_mode == 'strict':
            if not rec.boq_item_id:
                raise UserError(_("… requires a BOQ Item."))
        elif not rec.boq_item_id and not rec.item_ids:
            raise UserError(_("… must cover at least one BOQ item."))
```

A draft with nothing yet is allowed; it simply cannot advance. This matches how Odoo core gates (e.g. a sale order needs lines to confirm, not to save as draft).

## ⚠️ Pitfalls

- **A green test can hide it**: any test that passes one trigger field makes the constraint fire, so the gap only shows when a test creates the record with none of them. Add exactly that test.
- If you genuinely need save-time enforcement, override `create()`/`write()` instead — but a lifecycle gate is usually the better UX (draft can be incomplete).
- Keep `@api.constrains` for the *edit* path (it fires fine when the user changes one of the fields) as a secondary net if you like, but never as the sole enforcement.
- Don't reach for `required=True` conditionally — the DB NOT NULL is unconditional; conditional-required must be Python.

## Verification

Create the record omitting every scope field, assert save succeeds, then assert the lifecycle action raises.

## References

- Hit in `construction_project` v17.0.1.24.0 — `project.work.order` scope check moved from `@api.constrains _check_has_scope` to `action_confirm._check_scope_ready` (multi-item work order unification)
- Related file: `orm/onchange-only-computation-breaks-nonform-create.md`
