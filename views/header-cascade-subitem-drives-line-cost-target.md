# Header Sub-Item Cascade Driving Line-Level Cost Target (level-1 → level-2 → filtered lines)

**Category:** Views
**Tags:** #views, #cascade, #hierarchy, #onchange, #domain, #computed-fields, #backward-compat, #boq
**Severity:** 🟡 Medium
**Last Verified:** 2026-07-11
**Odoo Versions:** 17

## Problem
A work order picks a top-level BOQ item (`boq_item_id`, level 1). The user wants a guided
**cascade**: after the main item, pick a specific sub-item (level 2/3) in the header, and
have the material/labor/equipment lines (each with a `boq_target_id` "Cost Booked To") be
**scoped and defaulted to that sub-item's breakdown only** — not the whole item subtree.
The cascade should apply **only in strict cost-control mode**; flexible mode must behave
exactly as before. And it must not break existing work orders (which have no sub-item).

Naively repointing every line compute from the header item to a new sub-item field, plus
making the sub-item `required` via `@api.constrains`, causes two traps: (a) the same
"which BOQ node do I book under" logic gets duplicated across 3 models × 3 methods, and
(b) an `@api.constrains` on the newly-required field **retroactively invalidates legacy
records** — any unrelated save on an old strict work order without a sub-item now raises.

## Solution ✅
**1. One helper resolves the "cost target root" — repoint every compute at it.**
Add a single method on each cost-line model; the allowed-set, the default, and the
in-plan check all call it, so the cascade is a one-line change per compute:

```python
def _cost_target_root(self):
    """The BOQ node cost is booked under: strict → the work order's chosen sub-item,
    else the work order's main BOQ item."""
    self.ensure_one()
    wo = self.work_order_id
    if self.cost_control_mode == 'strict' and wo.boq_subitem_id:
        return wo.boq_subitem_id
    return wo.boq_item_id
```
Then `allowed_boq_target_ids = search([('id','child_of', rec._cost_target_root().id)])`,
the `boq_target_id` default resolves its breakdown leaves under `_cost_target_root()`, etc.
Add `'work_order_id.boq_subitem_id'` and `'cost_control_mode'` to each `@api.depends` so
re-picking the sub-item re-targets the lines (the default compute has no
`if not boq_target_id` guard, so it overwrites on root change — which is what "the whole
work order focuses on one sub-item" wants).

**2. The header cascade field: descendant domain lives in the VIEW, gated on mode.**
The field's dynamic domain references another header field, so it MUST be a view attribute
(a Python `fields.Many2one(domain=...)` kwarg is static and can't see `boq_item_id`):

```xml
<field name="cost_control_mode" invisible="1"/>
<field name="boq_subitem_id"
       domain="[('id','child_of',boq_item_id),('id','!=',boq_item_id),('display_type','=',False)]"
       invisible="cost_control_mode != 'strict'"
       required="cost_control_mode == 'strict'"
       options="{'no_create': True}"/>
```
Add a related `cost_control_mode` on the header model to drive `invisible`/`required`.

**3. Enforce the newly-required header field as a COMPLETION GATE, not @api.constrains.**
```python
if rec.project_id.profile_id.cost_control_mode == 'strict':
    if not rec.boq_subitem_id:
        raise UserError(_("Strict cost control: pick the Sub-Item (Cost Focus) ... before completing."))
```
A `UserError` at the workflow step (`action_complete`) is a *business block* (correct per
Odoo convention) and only fires when it matters — legacy/draft records are never
retroactively blocked on unrelated edits. Keep the view-level `required` for new-record UX.

**4. Keep the sub-item inside the item subtree on re-pick.**
```python
@api.onchange('boq_item_id')
def _onchange_boq_item_reset_subitem(self):
    sub, item = self.boq_subitem_id, self.boq_item_id
    if sub and not (item and sub.parent_path and item.parent_path
                    and sub.parent_path.startswith(item.parent_path)):
        self.boq_subitem_id = False
```
`parent_path` prefix test (with the trailing `/`) is the cheap "is-descendant" check — no
extra search.

## ⚠️ Pitfalls
- **No migration needed — and don't add one that recomputes.** Because `boq_subitem_id`
  defaults empty on existing rows, `_cost_target_root()` returns the main item exactly as
  before, so stored `boq_target_id` on legacy lines is **not** recomputed on upgrade (Odoo
  only recomputes a stored dependent when a dependency VALUE changes, not because the
  `@api.depends` list grew or a brand-new field appeared as null). Writing the field in a
  migration would *trigger* the overwrite you're trying to avoid. Verify: after `-u`, count
  existing records with the new field set (must be 0) and confirm each legacy line still has
  its `boq_target_id`.
- **@api.constrains on a newly-required field breaks legacy data.** Use a workflow-step
  `UserError` (completion gate) instead; reserve `ValidationError`/`constrains` for true
  data-integrity invariants that must hold for ALL rows including historical ones.
- **Dynamic domain must reach the arch.** After adding `domain="... child_of boq_item_id"`
  in the view, confirm it via `Model.get_view(view_id,'form')['arch']` — a typo in the
  referenced header field name fails silently at eval time (swallowed by the client), not
  as a load-time XML error. (Same rule as [scope-many2one-to-cross-model-set-with-computed-m2m-domain].)
- **Non-work-order (tagged) lines:** `_cost_target_root()` returns an empty recordset when
  `work_order_id` is unset (distributed data-entry lines), so the default compute preserves
  the directly-set `boq_target_id` (`... or rec.boq_target_id`) instead of clobbering it.
  Confirm the distributed/source-capture tests still pass.
- **A new completion gate silently changes which error later-gate tests hit.** Inserting the
  sub-item `UserError` near the TOP of a multi-check `action_complete` means a pre-existing
  test for a LATER gate (e.g. the work-package budget block) now hits the sub-item gate
  first — and if its assertion is loose (`assertIn('Strict cost control', ...)`, which
  matches BOTH messages) it keeps passing green while testing nothing real. When you add an
  early gate, grep the tests that call the method and either satisfy the new gate in their
  setup (here: pass a valid `boq_subitem_id`) or tighten their assertion to a string unique
  to the gate they actually target (`assertIn('over budget by', ...)`).

## Related
- `views/scope-many2one-to-cross-model-set-with-computed-m2m-domain.md` — the base pattern
  (computed allowed-set + conditional view domain + mode toggle) this cascade builds on.
- `orm/hierarchical-actual-cost-rollup-must-be-additive.md` — why booking to a specific
  sub-item still rolls up correctly (additive, no double count).
