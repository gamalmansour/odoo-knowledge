# Work Order Strict Cost Control Sub-Item Cascade and Cost Line Validation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `work_order`, `cost_control`, `strict_mode`, `boq_subitem`, `cbs`

---

## Problem

When confirming and completing a Work Order (`project.work.order`) on a project configured with strict cost-control mode (`cost_control_mode == 'strict'`), the completion fails with the following blocking error:

```text
odoo.exceptions.UserError: This work order has out-of-plan cost lines awaiting Cost Management approval. Approve them (or book them to a planned line) before completing.
```

## Root Cause

In strict cost-control mode, the project profile enforces work-package level budget and scope control:
1. The work order requires both a root `boq_item_id` (the work package) and a specific `boq_subitem_id` (the cost focus package).
2. The cost lines (labor, equipment, material) resolve their allowed targets from `_cost_target_root()`, which points directly to `wo.boq_subitem_id`.
3. `_strict_target_leaves()` inspects all descendants under `wo.boq_subitem_id` matching the cost category (`labor`, `equipment`, or `material`).
4. If a cost line has its `boq_target_id` pointing to a leaf outside `wo.boq_subitem_id` (for example, `boq_subitem_id` is set to `.1` Material Package, but a labor line is added pointing to a leaf under `.2` Labor Package), the system flags the line as `is_in_plan = False` and `needs_cost_approval = True`.
5. `action_complete()` strictly blocks when any unapproved out-of-plan cost lines exist.

## Solution ✅

### 1. Dynamic Sub-Item Targeting via Parent Leaf Linkage
When creating or generating work orders programmatically or via UI, derive the `boq_subitem_id` directly from the intended breakdown leaf:

```python
# Select the breakdown leaf to book costs against
labor_target = env['project.boq.item'].search([
    ('id', 'child_of', root.id),
    ('breakdown_type', '=', 'labor'),
    ('child_ids', '=', False)
], limit=1)

# Ensure the sub-item is the exact parent package containing the leaf
subitem = labor_target.parent_id

wo = env['project.work.order'].create({
    'project_id': project.id,
    'boq_item_id': root.id,
    'boq_subitem_id': subitem.id,
    'engineer_id': engineer.id,
    'work_date': fields.Date.today(),
    'description': 'Execution description',
    'quantity_executed': executed_qty,
    'labor_ids': [(0, 0, {
        'labor_type': 'skilled',
        'description': 'Direct crew',
        'count': 6,
        'hours': 8.0,
        'rate': 140.0,
        'boq_target_id': labor_target.id,
    })],
})
wo.action_confirm()
wo.action_start()
wo.action_complete()
```

### 2. Multi-Discipline Package Separation
If a work package requires both direct labor and equipment residing in different CBS sub-packages, create dedicated work orders for each discipline:
- One work order targeting `Package.Labor` for site crew hours.
- One work order targeting `Package.Equipment` for machinery operation.

### 3. Subcontractor Cost Rollup
For items executed via subcontracting (`execution_method == 'subcontract'` or `breakdown_type == 'subcontractor'`), do not mix direct labor work orders unless intentional. Execute via Subcontractor Progress Invoices (`contract.subcontractor.invoice`):
- Approved and invoiced progress lines automatically roll up `qty_executed` and `actual_cost` to the parent BOQ item without triggering work-order approval gates.

## ⚠️ Pitfalls

- **Do NOT guess subitem suffix (.1 / .2):** Projects often have variable tree depths (e.g., `.1` Material, `.2` Rebar, `.3` Equipment & Labor). Always resolve `subitem` dynamically via `target_leaf.parent_id`.
- **Material Issue Valuation:** Material lines on work orders invoke `action_issue_material()`, requiring available stock in the project's internal location. For non-stock items or progress-only tracking, use labor/equipment or subcontractor progress invoices.
- **Set Union on Executed Quantity:** A root BOQ item accumulates executed quantity from all its completed child work orders through set union `(rec.work_order_ids | rec.sub_work_order_ids)` to prevent double counting.

## Verification

Run verification in Odoo shell:

```python
wo = env['project.work.order'].browse(wo_id)
assert not wo.labor_ids.filtered('needs_cost_approval'), "Labor lines must be in-plan!"
assert not wo.equipment_ids.filtered('needs_cost_approval'), "Equipment lines must be in-plan!"
assert wo.state == 'completed', "Work order completed successfully!"
```

## References

- Related: `boq_hierarchical_progress.md`
- Core Models: `construction_project/models/project_work_order.py`, `construction_project/models/project_labor_record.py`
