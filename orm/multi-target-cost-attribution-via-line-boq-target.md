# Let One Work Order Cover Several BOQ Items Without Corrupting Budget: Attribute Cost at the LINE, Not the Header

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `cost-attribution`, `budget`, `work-order`, `one2many`, `computed-rollup`, `design`

---

## Problem

A work order (or any cost-collector: manufacturing order, task, timesheet) is modelled as covering ONE cost object (`boq_item_id` m2o, required). The client now wants one work order to deliver SEVERAL BOQ items in a day's mixed work. The fear: "if a work order books labour/material across several items, how do we split the cost so each item's budget variance is right?"

The wrong instinct is to add an **allocation engine** — percentages that apportion a lump work-order cost across items — which needs its own sum-to-100 constraint, is error-prone, and hides where money actually went.

## Root Cause / Key Insight

If cost already lives on **cost lines** (labour, equipment, material as one2many), and each line carries a `boq_target_id` ("Cost Booked To"), then **cost attribution is already per-line, not per-work-order** — the work-order header item is only a *default* for new lines, not the thing costs roll up through. The BOQ item's `actual_cost` should sum the lines booked to it, not the work orders whose header points at it.

Check before designing: does the item's actual cost read `work_order.boq_item_id` or `cost_line.boq_target_id`? If the latter, multi-item is 80% done already.

## Solution ✅

Keep the header item (backward compatible — no migration, existing single-item records untouched) and add the rest alongside:

```python
# 1. Additional-items table (primary stays on the header)
class ProjectWorkOrderItem(models.Model):
    _name = 'project.work.order.item'
    work_order_id = fields.Many2one('project.work.order', required=True, ondelete='cascade')
    boq_item_id   = fields.Many2one('project.boq.item', required=True)
    quantity_executed = fields.Float()
    state = fields.Selection(related='work_order_id.state', store=True)   # for the qty roll-up

# 2. "All covered items" = primary | additional
all_boq_item_ids = fields.Many2many(compute=...)   # boq_item_id | item_ids.boq_item_id

# 3. Widen the cost line's allowed target set to every covered item's subtree
def _cost_target_roots(self):
    wo = self.work_order_id
    if self.cost_control_mode == 'strict' and wo.boq_subitem_id:
        return wo.boq_subitem_id                       # strict stays single-focus
    return wo.boq_item_id | wo.item_ids.boq_item_id    # flexible: all covered

# 4. Item.qty_executed sums BOTH header contribution AND additional-coverage lines
qty = sum(w.quantity_executed for w in self.work_order_ids if w.state=='completed') \
    + sum(l.quantity_executed for l in self.wo_item_ids if l.state=='completed')

# 5. Completion quantity control iterates covered items, each vs its own plan
for item, this_qty in wo._covered_item_quantities():
    if item.qty_executed + this_qty > item.quantity: ...
```

A genuinely shared cost is **split into lines** (6h to item A, 2h to item B) — explicit, auditable, and how SAP/Primavera actually book actuals. No apportionment maths.

## ⚠️ Pitfalls

- **`actual_cost` needs no change** if it already rolls up via `boq_target_id` — resist "fixing" it. Only `qty_executed` (which read the header) needs the additional-coverage term added, plus its `@api.depends`.
- **Scope the feature to flexible mode.** A strict single-cost-focus mode (`boq_subitem_id` cascade) has no defined budget/quantity semantics for extra items — reject additional items there with a constraint rather than inventing rules.
- **Guard duplicates**: an item must not be both the primary and an additional item, nor listed twice, or its executed quantity double-counts.
- **Backward compatibility for free**: keep the header m2o required; a single-item work order just has an empty additional-items o2m. No data migration.
- **Completion accounting in tests**: `action_complete()` here demands a cost journal + WIP + cost accounts on the profile; a success-path test must configure them (a block-path test that only asserts the raise never reaches that code, which is why the existing tests didn't need it).

## Verification

Two items on one work order, split a labour cost between them, complete, then assert each item's `actual_cost` AND `qty_executed` independently; assert an overrun on the *additional* item blocks completion while the primary is fine.

## References

- Implemented in `construction_project` v17.0.1.23.0 — `models/project_work_order_multi_item.py`, edits to `project_boq_item.py` (`qty_executed`), the 3 cost models (`_cost_target_roots`), and `project_work_order.py` (`action_complete` qty loop). `tests/test_multi_item_work_order.py` (13 tests).
- Related file: `orm/self-referential-stored-compute-across-siblings-reads-zero.md`
