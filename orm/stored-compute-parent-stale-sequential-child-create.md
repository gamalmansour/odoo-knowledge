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

## Root Cause 🎯 (found later — `recursive=True`)
The startup log had been saying it all along:

```
UserWarning: Field tender.boq.breakdown.unit_cost should be declared with recursive=True
```

`unit_cost` depends on `child_ids.total_cost` while `total_cost` depends on
`unit_cost` — the pair transitively depends on **itself through the
parent/child relation**. When such a field is declared WITHOUT
`recursive=True`, Odoo **truncates the recursive branch of the trigger tree**:
a change on a child propagates one hop and then silently stops, so ancestors
(and anything depending on them, like the BOQ line's own unit cost) are never
marked for recompute. Symptoms: import-time partial sums AND live UI edits on
Level 3 updating Level 2 but never reaching Level 1.

## Solution ✅
1. Declare **both** fields of the recursive pair with `recursive=True`
   (one of them alone is NOT enough — verified empirically):

```python
unit_cost  = fields.Float(compute='_compute_unit_cost',  store=True,
                          readonly=False, recursive=True)
total_cost = fields.Float(compute='_compute_total_cost', store=True,
                          recursive=True)
```

With this, the L3 → L2 → L1 cascade works live (verified: editing a child's
cost updated the parent AND the grand-parent line in the same transaction).

2. Belt-and-braces for import wizards — after the whole hierarchy is created,
   explicitly recompute the parents that have children:

```python
parents = created_breakdowns.filtered('child_ids')
if parents:
    parents._compute_unit_cost()   # deterministic, bottom-up
```

3. For top-level records whose cost may come either from the sheet or from
   children, only write the manual value **at the end, and only if no children
   were created** (`if not line.breakdown_ids: line.unit_cost = sheet_value`),
   so the compute owns the value whenever a breakdown exists.

## Bonus pitfall — one2many shows children too
If Level 3 rows also carry the Level 1 inverse FK (`boq_line_id`), the plain
`One2many` on the line shows **L2 and L3 mixed** in the form page, and any
column `sum` double-counts (details counted once inside their parent's total
and once as rows). Fix by putting a domain on the field definition itself
(applies at ORM read, unlike a view-level domain on one2many which is ignored):

```python
breakdown_ids = fields.One2many('tender.boq.breakdown', 'boq_line_id',
                                domain=[('parent_id', '=', False)])
```

This also fixed a latent template-copy duplication (`_copy_breakdown` used to
copy L3 twice: once as child, once as root).

## ⚠️ Pitfalls
- **Never ignore `should be declared with recursive=True` warnings** — they
  mean the trigger tree is being truncated and stored values WILL go stale.
- `recursive=True` must go on every field participating in the cycle, not
  just the one named in the warning.
- Do NOT pass a manual value for the editable compute at parent `create()` and
  rely on the children to fix it later.
- Verify with **distinct** numbers per child; identical sums (2×50 vs manual
  100) masked the bug in the first repro attempt.
- Other modules in the same suite still warn (`contract.boq.breakdown.total_cost`,
  `contract.amendment.breakdown.new_price`, `project.boq.item.full_code`) —
  same fix applies.

## Related
- `one2many_import_boq.md` (button-driven hierarchical import pattern)
- `stored-compute-incomplete-depends-silent-staleness.md`
