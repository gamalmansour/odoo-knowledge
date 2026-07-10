# Redistributing a stored cost aggregate: verify the TOTAL is preserved (Σsources == Σsinks), not just that tests pass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `rollup`, `money`, `attribution`, `verification`, `migration`

---

## Problem

You change how a stored `actual_cost` is *attributed* — e.g. work-order cost lines used to
book onto the work order's BOQ item, now they book onto a per-category breakdown line
(`boq_target_id`), and a second, independent dimension (a WBS aggregate) reads the same
numbers. A green unit-test suite on synthetic data does NOT prove real data is intact: an
interacting aggregate can silently double-count or drop cost only on production-shaped data
(nested parents, items with no dimension set, multiple lines per key).

## Root Cause

Redistribution changes *where* each cost lands, and two stored aggregates over the same
lines (here BOQ-by-category and WBS-by-node) couple through the shared `actual_cost`
baseline. Unit tests assert per-node values on a clean fixture; they can't see a
double-count that only arises from the historical mix.

## Solution ✅

After the change + migration, run a **conservation check on real data**: the sum of the
SOURCE line costs must equal the sum of what the SINKS booked. Equal ⇒ pure redistribution
(safe); unequal ⇒ double-count or loss.

```python
# A: every completed work-order cost line (the sources)
A = sum(l.total_cost
        for m in ('project.material.issue', 'project.labor.record', 'project.equipment.record')
        for l in env[m].search([]) if l.work_order_id.state == 'completed')

# B: what each BOQ item booked to itself (the sinks)
B = 0.0
for b in env['project.boq.item'].search([]):
    for lines in (b.material_target_ids, b.labor_target_ids, b.equipment_target_ids):
        B += sum(l.total_cost for l in lines if l.work_order_id.state == 'completed')

assert abs(A - B) < 0.01          # equal => no double count, no loss
```

Then spot-check that pre-existing per-node totals of the OTHER dimension (WBS) are unchanged,
and that no `actual_cost` went negative. A new non-zero node appearing is fine **iff** the
conservation check holds — it's cost that was previously unattributed, now attributed.

## ⚠️ Pitfalls

- Do NOT "verify" by summing every node of a recursive tree — parents include children, so
  the sum double-counts the hierarchy and tells you nothing. Compare SOURCES vs SINKS at the
  leaf/booking granularity.
- Passing tests + "the demo looks right" is not enough for money code — the conservation
  identity is the real gate.
- Two independent per-line dimensions (WBS + cost category here) should each be a parallel
  aggregation of the same line costs; keep them decoupled so one's change can't inflate the
  other. See [[hierarchical-actual-cost-rollup-must-be-additive]] and
  [[new-stored-field-feeding-subtractive-rollup-needs-backfill-migration]].

## Verification

`odoo-bin -u <module> --test-enable --test-tags /<module>` (all green) **and** the A==B
conservation check above on a database with history.

## References

- Related file: `orm/hierarchical-actual-cost-rollup-must-be-additive.md`
