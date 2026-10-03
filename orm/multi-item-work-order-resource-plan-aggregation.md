# Multi-Item Work Order Resource Plan Aggregation (Header vs Tabbed Lines)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `construction`, `work-order`, `multi-item`, `resource-plan`, `compute`, `boq`

---

## Problem

When budgeting and tracking construction resources (labor, equipment, materials) allocated to specific Bill of Quantities (BOQ) items via a resource plan (`project.resource.plan`), actual site execution costs and quantities appear as `0.0` or fail to accumulate even though site work orders have been executed and completed.

```python
# Symptom in project.resource.plan:
actual_qty = 0.0
actual_cost = 0.0
variance = planned_cost  # Looks completely unexecuted!
```

## Root Cause

In modern construction ERP modules, daily Work Orders frequently operate in a **flexible multi-item mode** where multiple BOQ items are executed within a single work order (represented in a One2many tab, e.g. `item_ids.boq_item_id`), leaving the single header field `work_order_id.boq_item_id` set to `False`.

If the resource plan compute method naively filters cost records using only the direct header relationship:

```python
# ❌ BUGGY PATTERN:
domain = [('work_order_id.boq_item_id', '=', rec.boq_item_id.id)]
```

Any labor, equipment, or material lines incurred under tabbed/multi-item work orders are completely missed, causing the actual costs to evaluate to `0.0`.

## Solution ✅

When aggregating actual site records by BOQ item, query the matching work orders using an OR condition (`'|'`) between the header BOQ item and the nested multi-item lines:

```python
# ✅ CORRECT PATTERN:
matching_wos = self.env['project.work.order'].search([
    ('project_id', '=', rec.project_id.id),
    ('state', '!=', 'cancelled'),
    '|',
    ('boq_item_id', '=', rec.boq_item_id.id),
    ('item_ids.boq_item_id', '=', rec.boq_item_id.id),
])
domain = [('work_order_id', 'in', matching_wos.ids)]

if rec.resource_type == 'labour':
    records = self.env['project.labor.record'].search(domain)
    actual_qty = sum(r.count * r.hours for r in records)
    actual_cost = sum(records.mapped('total_cost'))
elif rec.resource_type == 'equipment':
    records = self.env['project.equipment.record'].search(domain)
    actual_qty = sum(records.mapped('hours'))
    actual_cost = sum(records.mapped('total_cost'))
elif rec.resource_type == 'material':
    records = self.env['project.material.issue'].search(domain)
    actual_qty = sum(records.mapped('quantity'))
    actual_cost = sum(records.mapped('total_cost'))
```

## ⚠️ Pitfalls

- **Cancelled Work Orders**: Always exclude cancelled work orders (`('state', '!=', 'cancelled')`) so voided transactions do not skew actual resource consumption.
- **Search View Filters on Non-Stored Fields**: Do **not** place non-stored computed fields (such as `variance` or `actual_cost`) inside XML `<filter domain="[('variance', '<', 0)]"/>` unless a corresponding `search=` function is defined on the model field; otherwise Odoo raises an `odoo.tools.convert.ParseError` during view validation on startup.

## Verification

Run test suite ensuring actual execution rolls up from both header-bound and tab-bound work orders:

```bash
odoo-bin -c odoo.conf -d db_name -u construction_project --test-enable --test-tags /construction_project:TestResourcePlan --stop-after-init
```
