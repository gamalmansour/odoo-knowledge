# Hierarchical Progress Calculation in BOQ

**Category**: Development  
**Tags**: compute, progress, boq, hierarchy  
**Odoo Versions**: 17.0+  
**Last Verified**: 2026-10-14

## 📝 Problem Definition
In a multi-level Bill of Quantities (BOQ), tracking progress at leaf nodes using `qty_executed / quantity` works for standalone lines. However, BOQ models often serve a dual purpose:
1. **Hierarchical WBS / Summary Nodes**: parent nodes with sub-deliverables (`child_ids`) where progress is a budget-weighted earned value.
2. **Cost Breakdown Structure (CBS)**: deliverable BOQ items that have their own planned physical quantity (`quantity`), but also have child breakdown packages (`child_ids` for material, labor, equipment). In this case, work orders are executed directly on the BOQ item (`qty_executed`), while the children are cost breakdown lines without direct work orders.

Unconditionally branching on `if rec.child_ids:` causes items with CBS breakdowns to ignore their direct physical progress, locking `progress_percentage` at 0%!

## ✅ Solution & Best Practice
Compute both direct physical progress and child earned-value roll-up, taking `max(direct_prog, earned_prog)` capped at 100%:

```python
@api.depends('qty_executed', 'quantity', 'child_ids.progress_percentage', 'child_ids.budget_amount', 'budget_amount')
def _compute_progress_from_qty(self):
    for rec in self:
        direct_prog = 0.0
        if rec.quantity and rec.qty_executed:
            direct_prog = min((rec.qty_executed / rec.quantity) * 100.0, 100.0)

        earned_prog = 0.0
        if rec.child_ids:
            if rec.budget_amount > 0:
                earned_value = sum(child.budget_amount * (child.progress_percentage / 100.0) for child in rec.child_ids)
                earned_prog = min((earned_value / rec.budget_amount) * 100.0, 100.0)
            else:
                priced = rec.child_ids.filtered(lambda c: c.progress_percentage > 0)
                earned_prog = (sum(priced.mapped('progress_percentage')) / len(priced)) if priced else 0.0

        rec.progress_percentage = max(direct_prog, earned_prog)
```

## ⚠️ Pitfalls
- **The CBS Breakdown Trap:** If an item has child breakdown packages (imported from contract tender breakdown), work orders are logged against `wo.boq_item_id`. If `_compute_progress_from_qty` branches solely on `if rec.child_ids:`, the parent item will evaluate to `0.0%` because the breakdown lines have no direct work orders of their own.
- **Sub-Item Work Order Linkage:** In strict cost-control mode, `wo.boq_subitem_id` points to the breakdown package. Ensure `project.boq.item` defines `sub_work_order_ids = fields.One2many('project.work.order', 'boq_subitem_id')` and uses union `(rec.work_order_ids | rec.sub_work_order_ids)` in `_compute_qty_executed` to prevent double-counting.
- **Division by Zero:** Always check if `total_budget > 0` or `quantity > 0` before division.
- **Recursive Dependency Missing:** Ensure you include `child_ids.progress_percentage` and `child_ids.budget_amount` in `@api.depends` so the parent updates automatically when a sub-item changes.
- **Max limit:** Progress should technically not exceed 100%, hence `min(..., 100.0)`.
- **`qty_executed` Overwrite Trap:** Never write directly to `qty_executed` in demo data or migration scripts. `qty_executed` is a computed field:
  - For `execution_method == 'direct'`, it requires completed `project.work.order` (`quantity_executed`).
  - For `execution_method == 'subcontract'`, it requires approved/invoiced `contract.subcontractor.invoice.line` linked via `boq_item_id`.
  Direct assignment without these records will be wiped back to `0.0` on the next ORM recompute or flush.
- **IPC Financial Rollup States:** In `contract.owner`, `total_billed` aggregates progress invoices where `state in ('approved', 'invoiced')`. Do NOT set custom states like `'paid'` directly on `contract.progress.invoice` because that will exclude them from the contract's billed total and project's `revenue_billed`.
