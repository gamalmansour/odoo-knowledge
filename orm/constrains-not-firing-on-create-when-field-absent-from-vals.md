# `@api.constrains` Does NOT Reliably Fire on `create()` for a Field Absent From `vals`

**Category:** ORM
**Tags:** #orm, #constrains, #create, #validation, #gotcha
**Severity:** 🔴 Critical
**Last Verified:** 2026-07-09
**Odoo Versions:** 17 (behavior likely applies to 16-19, verify per version if it matters)

## Problem
Widely assumed (and asserted in some Odoo community write-ups): "`@api.constrains`
methods run after EVERY `create()`, regardless of which fields were passed in
`vals` — unlike `write()`, where the listed fields must actually be dirtied."
**This is not what was observed empirically in this codebase.**

Added `@api.constrains('boq_item_id')` on a line model, to require a BOQ item
whenever the parent requisition's `request_type == 'project'`. Verified with a
manual test:
```python
line = Line.create({'requisition_id': req.id, 'description': 'x', 'qty': 1,
                    'product_id': prod.id})   # boq_item_id NOT in vals
# -> create() succeeds silently, no ValidationError
line._check_boq_item_required_for_project_type()   # called manually
# -> DOES raise ValidationError (the logic itself is correct)
```
The constrain method's logic was correct — but the ORM never AUTO-INVOKED it
during `create()`, because `boq_item_id` was absent from `vals` (it stayed at
its column default of `False`). The trigger-field list evidently gates
`create()`-time re-validation the same way it gates `write()`-time
re-validation — presence in vals matters in BOTH cases, contrary to the
"create validates everything" assumption.

## Solution ✅
List a field that is GUARANTEED to be present in `vals` on every create
(typically a `required=True` field like the parent Many2one) ALONGSIDE the
field you actually care about:

```python
@api.constrains('boq_item_id', 'requisition_id')
def _check_boq_item_required_for_project_type(self):
    for rec in self:
        if rec.requisition_id.request_type == 'project' and not rec.boq_item_id:
            raise ValidationError(_("Please select a BOQ Item for this line: ..."))
```

`requisition_id` is `required=True` and therefore always explicitly present in
`vals` on every create — its presence is what reliably triggers the constrain
check on create, after which the method body freely reads `boq_item_id` (which
doesn't need to have been in vals for the BODY to see its correct/default
value — only the TRIGGER-field presence-in-vals matters for whether the check
runs at all).

## ⚠️ Pitfalls
- **Never trust "constrains always run on create" as a blanket assumption.**
  Verify empirically (create WITHOUT the field in vals, confirm the exception
  actually raises) rather than assuming from memory or general folklore.
- The safest, most future-proof pattern for "field X required under condition
  Y" constrains: always include at least one `required=True` field from the
  SAME model in the trigger list (often the one the condition itself depends
  on, e.g. a parent Many2one whose related field drives the condition), even
  if that field's own value isn't directly used in the raise logic.
- This compounds with the earlier-documented o2m-trigger limitation
  (`independent-control-policies-not-one-guard.md` sibling family): a
  HEADER-level constrain listing a `one2many` field name only fires when lines
  are written THROUGH the parent (bundled `(0,0,...)`/`(1,id,...)` commands in
  the parent's own `write()`), not when a child is created directly via the
  line model. For a rule needing airtight coverage of every creation path
  (parent-mediated AND direct child-side), you need BOTH: the header-level
  o2m-triggered constrain (catches header field switching after lines exist)
  AND a line-level constrain with a guaranteed-present trigger field (catches
  direct child creation) — neither alone is sufficient.
- Verify with the REALISTIC path a real user would exercise (form save = parent
  `write()` with nested o2m commands), not just a raw `Model.create()` on the
  child — the two are genuinely different code paths with different trigger
  behavior, and testing only one can give false confidence.

## Verification (rolled back)
7 scenarios covering domain restriction, onchange auto-fill, direct child
create without the field (blocked after fix, was silently allowed before),
direct child create with the field (succeeds), parent-write form-save path
without the field (blocked), internal mode (unaffected, no requirement), and
switching an existing header from internal→project with a pre-existing
boq-item-less line (blocked by the header-level o2m constrain).
