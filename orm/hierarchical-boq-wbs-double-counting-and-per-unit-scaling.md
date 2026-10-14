# Hierarchical BOQ Items Linked to a WBS Node Double-Counting Budgets & Per-Unit Breakdown Scaling

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `hierarchy`, `wbs`, `boq`, `double-counting`, `rollup`, `money`

---

## Problem

1. **WBS Double/Triple Counting**: When a hierarchical item model (`project.boq.item` with `parent_id` / `child_ids` across 3 levels: `Level 1 -> Level 2 -> Level 3`) already rolls up `budget_amount` and `actual_cost` from children to parents, and all 3 levels are linked via `wbs_id` to the same `project.wbs` node (so leaf items carry `wbs_id` for work-order auto-generation), summing `rec.boq_item_ids.mapped('budget_amount')` on `project.wbs` sums Level 1 + Level 2 + Level 3, **tripling** the WBS budget and actual cost.
2. **Per-Unit Breakdown Quantity Scaling on Hand-off**: When `tender.boq.line` uses `'per_unit'` breakdown calculation mode (where Level 2/3 breakdown quantities represent the resource rate per `1.0` unit of the Level 1 line), copying `breakdown.quantity` directly into `project.boq.item` without multiplying by `line.qty_contracted` causes `project.boq.item.budget_amount` (which sums children budgets directly) to reflect the cost of **1 unit** instead of the total contracted quantity.

## Root Cause

- `project.boq.item._compute_budget` computes `rec.budget_amount = sum(rec.child_ids.mapped('budget_amount'))` for parent nodes, whereas `tender.boq.line._compute_unit_cost` treats `sum(level2.total_cost)` as the **unit cost** and multiplies by `rec.quantity`.
- `project.wbs.boq_item_ids` is a flat `One2many` containing every `project.boq.item` whose `wbs_id == rec.id`, regardless of whether its `parent_id` is also in `rec.boq_item_ids`.

## Solution ✅

### 1. Filter to Top-Most Subtree Roots Inside `project.wbs._compute_wbs_costs`
```python
@api.depends('boq_item_ids.budget_amount', 'boq_item_ids.actual_cost', 'boq_item_ids.parent_id', ...)
def _compute_wbs_costs(self):
    for rec in self:
        top_boq_items = rec.boq_item_ids.filtered(
            lambda b: not b.parent_id or b.parent_id not in rec.boq_item_ids
        )
        own_budget = sum(top_boq_items.mapped('budget_amount'))
        own_actual = sum(top_boq_items.mapped('actual_cost'))
```

### 2. Scale Breakdown Quantities by `qty_contracted` When Importing in `per_unit` Mode
```python
calc_mode = self.env['ir.config_parameter'].sudo().get_param(
    'construction_tender.boq_quantity_calculation', 'per_unit'
)
qty_factor = line.qty_contracted if (calc_mode == 'per_unit' and line.qty_contracted > 0) else 1.0
self._import_boq_breakdown(top_breakdowns, boq_item, qty_factor=qty_factor)
```

## ⚠️ Pitfalls

- Always include `'boq_item_ids.parent_id'` in `@api.depends` of `_compute_wbs_costs` so reparenting a BOQ item triggers WBS recomputation.
- Propagate `wbs_id` recursively to all descendants (`Level 1 -> Level 2 -> Level 3`) so leaf-only consumers (such as `_generate_work_orders_from_boq(mode='by_wbs')`) find `item.wbs_id` on leaf items.

## Verification

```python
# Sum of top-level WBS budgets must equal project.total_budget with 0 unlinked BOQ items:
assert abs(sum(wbs_parents.mapped('budget_amount')) - project.total_budget) < 0.01
```
