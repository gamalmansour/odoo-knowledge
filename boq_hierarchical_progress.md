# Hierarchical Progress Calculation in BOQ

**Category**: Development  
**Tags**: compute, progress, boq, hierarchy  
**Odoo Versions**: 17.0+  
**Last Verified**: 2026-10-02

## 📝 Problem Definition
In a multi-level Bill of Quantities (BOQ), tracking progress at leaf nodes (Level 3) using `qty_executed / quantity` works perfectly. However, parent nodes (Levels 1 and 2) do not have a uniform unit of measure or direct quantities, meaning standard sums or averages provide inaccurate results. 

## ✅ Solution & Best Practice
For parent items with sub-items (`child_ids`), progress must be calculated using a **Budget-Weighted Average**.

```python
@api.depends('qty_executed', 'quantity', 'child_ids.progress_percentage', 'child_ids.budget_amount', 'budget_amount')
def _compute_progress_from_qty(self):
    for rec in self:
        if rec.child_ids:
            total_budget = rec.budget_amount
            if total_budget > 0:
                weighted_progress = sum((child.progress_percentage * child.budget_amount) for child in rec.child_ids)
                rec.progress_percentage = min(weighted_progress / total_budget, 100.0)
            else:
                rec.progress_percentage = 0.0
        else:
            if rec.quantity:
                rec.progress_percentage = min((rec.qty_executed / rec.quantity) * 100.0, 100.0)
            else:
                rec.progress_percentage = 0.0
```

## ⚠️ Pitfalls
- **Division by Zero:** Always check if `total_budget > 0` or `quantity > 0` before division.
- **Recursive Dependency Missing:** Ensure you include `child_ids.progress_percentage` and `child_ids.budget_amount` in `@api.depends` so the parent updates automatically when a sub-item changes.
- **Max limit:** Progress should technically not exceed 100%, hence `min(..., 100.0)`.
- **`qty_executed` Overwrite Trap:** Never write directly to `qty_executed` in demo data or migration scripts. `qty_executed` is a computed field:
  - For `execution_method == 'direct'`, it requires completed `project.work.order` (`quantity_executed`).
  - For `execution_method == 'subcontract'`, it requires approved/invoiced `contract.subcontractor.invoice.line` linked via `boq_item_id`.
  Direct assignment without these records will be wiped back to `0.0` on the next ORM recompute or flush.
- **IPC Financial Rollup States:** In `contract.owner`, `total_billed` aggregates progress invoices where `state in ('approved', 'invoiced')`. Do NOT set custom states like `'paid'` directly on `contract.progress.invoice` because that will exclude them from the contract's billed total and project's `revenue_billed`.
