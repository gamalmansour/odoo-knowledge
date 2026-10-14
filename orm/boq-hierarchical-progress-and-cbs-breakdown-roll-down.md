# BOQ Hierarchical Progress and CBS Breakdown Execution Roll-Down

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `boq`, `cbs`, `wbs`, `progress_percentage`, `qty_executed`, `hierarchy`, `dag`, `circular-dependency`

---

## Problem

In construction ERP implementations with a multi-level Bill of Quantities (BOQ), items serve two complementary structures:
1. **WBS Deliverables (Parent Items)**: Aggregate progress bottom-up using budget-weighted Earned Value Management (EVM).
2. **Cost Breakdown Structure (CBS Packages & Leaves)**: Breakdown lines (`action_open_breakdown` in `view_project_boq_breakdown_tree`) representing concrete, rebar, equipment, or labor packages underneath a deliverable.

When opening the breakdown view (`view_project_boq_breakdown_tree`), all child packages and leaf items display `progress_percentage = 0.0%` even though the parent deliverable is 100% or 60% executed with confirmed work orders, material issues, and vendor bills. Conversely, if naive top-down inheritance is applied to `progress_percentage`, the ORM crashes with:
```
RecursionError: maximum recursion depth exceeded / ORM Cyclic Dependency DAG cycle
```

## Root Cause

1. **Missing Direct Headers on CBS Breakdown Lines**: Work orders and subcontractor contracts are executed at the main deliverable or package level (`wo.boq_item_id`). The leaf items (Level 3 resource lines) and intermediate packages do not each receive their own individual work order header. As a result, direct calculation of `qty_executed` evaluates to `0.0`.
2. **Circular Dependency Pitfall**: `progress_percentage` on parent items depends on `child_ids.progress_percentage`. If child `progress_percentage` is made to depend on `parent_id.progress_percentage`, an ORM Directed Acyclic Graph (DAG) cycle is created (`parent <-> child`), freezing or crashing the compute engine.

## Solution ✅

Decouple the direction of physical execution from the direction of earned-value percentage rollup:
1. **Top-Down Flow for Physical Execution (`qty_executed`)**:
   In `_compute_qty_executed()`, if an item has direct work orders or subcontractor invoices, sum them. If not, and it has a parent with non-zero quantity and execution, proportionally inherit the execution ratio from `parent_id`:
   ```python
   parent_ratio = min(rec.parent_id.qty_executed / rec.parent_id.quantity, 1.0)
   rec.qty_executed = parent_ratio * rec.quantity
   ```
2. **Bottom-Up Flow for Progress Percentage (`progress_percentage`)**:
   `progress_percentage` calculates direct progress from its own `qty_executed / quantity`, or aggregates bottom-up via earned value:
   `rec.progress_percentage = max(direct_prog, earned_prog)`
3. **Strictly Acyclic ORM Graph**:
   `qty_executed` flows top-down (`parent_id.qty_executed -> rec.qty_executed`).
   `progress_percentage` aggregates bottom-up (`child_ids.progress_percentage -> rec.progress_percentage`).
   No cyclic dependency exists in the DAG.

```python
# construction_project/models/project_boq_item.py

qty_executed = fields.Float(
    string='Executed Qty',
    compute='_compute_qty_executed',
    store=True,
    recursive=True,
    help='Executed quantity from direct work orders, subcontractor invoices, or inherited proportionally from parent CBS deliverable.'
)

@api.depends(
    'work_order_ids.state', 'work_order_ids.quantity_executed',
    'sub_work_order_ids.state', 'sub_work_order_ids.quantity_executed',
    'wo_item_ids.quantity_executed', 'wo_item_ids.work_order_id.state',
    'parent_id.qty_executed', 'parent_id.quantity', 'quantity'
)
def _compute_qty_executed(self):
    for rec in self:
        # 1. Direct work orders
        all_wos = (rec.work_order_ids | rec.sub_work_order_ids).filtered(lambda w: w.state == 'done')
        direct_wo_qty = sum(all_wos.mapped('quantity_executed'))

        # 2. Multi-item tabbed work orders
        tabbed_wo_qty = sum(rec.wo_item_ids.filtered(lambda l: l.work_order_id.state == 'done').mapped('quantity_executed'))

        # 3. Subcontractor approved invoices
        sub_invoice_lines = self.env['contract.subcontractor.invoice.line'].search([
            ('boq_item_id', '=', rec.id),
            ('invoice_id.state', 'in', ['approved', 'invoiced'])
        ])
        sub_qty = sum(sub_invoice_lines.mapped('quantity_current'))

        direct_total = direct_wo_qty + tabbed_wo_qty + sub_qty

        if direct_total > 0:
            rec.qty_executed = direct_total
        elif rec.parent_id and rec.parent_id.quantity > 0 and rec.parent_id.qty_executed > 0:
            parent_ratio = min(rec.parent_id.qty_executed / rec.parent_id.quantity, 1.0)
            rec.qty_executed = parent_ratio * rec.quantity
        else:
            rec.qty_executed = 0.0

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

- **Do NOT put `@api.depends('parent_id.progress_percentage')` on `progress_percentage`**: Since `progress_percentage` already depends on `child_ids.progress_percentage`, adding `parent_id.progress_percentage` creates a cyclic graph in Odoo's dependency resolver and will raise an ORM recursion error.
- **`recursive=True` Flag**: When a computed field reads its own field on `parent_id`, mark `qty_executed = fields.Float(..., recursive=True)` so Odoo optimizes cache invalidation across arbitrary tree depths.
- **Capping Ratio at 1.0**: Always use `min(parent_ratio, 1.0)` so potential over-execution on a parent does not inadvertently blow out sub-package quantities beyond 100% without explicit change orders.

## Verification

Run Odoo unit tests verifying both bottom-up EVM and top-down breakdown tree inheritance:
```bash
./odoo-bin -c odoo18_con.conf -d cons_demo --test-enable --stop-after-init -i construction_project --test-tags=TestProjectProgressWeighting
```

## References

- Related file: `orm/boq-three-level-breakdown-domain-actions.md`
- Related file: `orm/boq-item-nature-conditional-product-enforcement.md`
- Source module: `construction_project/models/project_boq_item.py`
