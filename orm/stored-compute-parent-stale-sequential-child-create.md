# Stored Parent Compute Goes Stale When Children Are Created Row-by-Row (Import Flows)

**Category:** ORM
**Tags:** #orm, #computed-fields, #store, #one2many, #import, #hierarchy, #boq
**Severity:** 🔴 Critical
**Last Verified:** 2026-07-08
**Odoo Versions:** 17 (likely 16-19)

## Problem
A parent model has a stored, editable compute that aggregates its children:

```python
unit_cost = fields.Float(compute='_compute_unit_cost', store=True, readonly=False)

@api.depends('child_ids.total_cost', 'quantity')
def _compute_unit_cost(self):
    for rec in self:
        if not rec.child_ids:
            continue  # keep manual value for leaves
        rec.unit_cost = sum(rec.child_ids.mapped('total_cost')) / rec.quantity
```

In the **UI** this works (the whole one2many arrives in a single `write`).
But in an **import wizard / shell script** that creates the parent first and then
each child with a **separate `create()` call**, the parent ends up with a *stale
partial sum* — empirically it froze at the value of the FIRST child only
(e.g. children 150 + 30 → parent stuck at 150). The trigger fires per child
creation, the compute runs mid-stream, and later children do not reliably
re-trigger it, especially when the parent was created with a manual value for
the editable compute field.

Observed while extending the `construction_tender` 3-level BOQ Excel import
(BOQ line → breakdown → sub-items): every Level 2 breakdown that had Level 3
children imported with a wrong/zero `unit_cost`, silently corrupting the whole
tender costing (Level 1 totals were off by the missing families).

## Solution ✅
After the whole hierarchy is created, explicitly recompute the parents that
have children, then let the totals cascade up through the normal depends chain:

```python
# after the import loop
parents = created_breakdowns.filtered('child_ids')
if parents:
    parents._compute_unit_cost()   # deterministic, bottom-up (children are leaves)
```

Direct assignment inside the compute marks the parents' dependent fields
(`total_cost`, then the BOQ line's own compute) as to-recompute, so Level 1
costs/prices come out correct on the next read/flush.

For top-level records whose cost may come either from the sheet or from
children, only write the manual value **at the end, and only if no children
were created** (`if not line.breakdown_ids: line.unit_cost = sheet_value`),
so the compute owns the value whenever a breakdown exists.

## ⚠️ Pitfalls
- Do NOT pass a manual value for the editable compute at parent `create()` and
  rely on the children to fix it later — that is exactly the stale case.
- Batch-creating all children in one `create([vals, ...])` reduces the window
  but the explicit final recompute is the only deterministic guarantee.
- This only works bottom-up in one pass when the hierarchy is bounded (here
  max 3 levels ⇒ parents' children are always leaves). For deeper trees,
  recompute level by level from the deepest.
- Verify with **distinct** numbers per child; identical sums (2×50 vs manual
  100) masked the bug in the first repro attempt.

## Related
- `one2many_import_boq.md` (button-driven hierarchical import pattern)
- `stored-compute-incomplete-depends-silent-staleness.md`
