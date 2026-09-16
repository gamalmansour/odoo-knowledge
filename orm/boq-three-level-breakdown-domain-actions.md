# Three-Level BOQ Breakdown Hierarchy with Domain-Separated Actions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `boq`, `breakdown`, `hierarchy`, `actions`, `domain`, `parent_id`, `rollup`

---

## Problem

In construction and EPC costing modules, users encounter an empty tree view when opening **All Sub-items (Level 3)** (`action_tender_boq_breakdown_level3`), while **Cost Breakdowns (Level 2)** (`action_tender_boq_breakdown_level2`) displays records normally.

Both actions point to the same model: `tender.boq.breakdown`.

## Root Cause

The architecture uses a 3-tier costing structure mapped across two models:
1. **Level 1 (BOQ Item):** `tender.boq.line` (e.g., Concrete Works, Excavation).
2. **Level 2 (Cost Breakdown):** `tender.boq.breakdown` with `parent_id = False` (Root components e.g., Rebar Supply, Bulk Cement, Excavator Time).
3. **Level 3 (Sub-items / Nested Breakdown):** `tender.boq.breakdown` with `parent_id != False` (Sub-components e.g., Raw steel bars, bending fees, transport).

The window actions are partitioned by domain:
- **Level 2 Action:** `domain="[('parent_id', '=', False)]"`
- **Level 3 Action:** `domain="[('parent_id', '!=', False)]"`
- **BOQ Costing Analysis (Pivot/Graph):** `domain="[('parent_id', '!=', False)]"`

When demo data or manual imports only seed root components without defining nested child records (`parent_id`), Level 3 and the Costing Analysis report naturally evaluate to 0 records.

## Solution ✅

### 1. Structure Child Records Properly
When defining Level 3 records in XML or via import, ensure both `parent_id` AND `boq_line_id` are populated:

```xml
<record id="rb_t1L4_rebar_raw" model="tender.boq.breakdown">
    <field name="parent_id" ref="rb_t1L4_rebar"/>
    <field name="boq_line_id" ref="construction_tender.boq_t1_L4"/>
    <field name="product_id" ref="construction_tender.prod_rebar"/>
    <field name="name">Raw High-Yield Deformed Bars</field>
    <field name="breakdown_type">material</field>
    <field name="quantity">1.05</field>
    <field name="unit_cost">1950.0</field>
    <field name="cost_code_id" ref="construction_costcode.cc_03_2"/>
</record>
```

### 2. Auto-Rollup to Level 2 Unit Cost
The parent model must compute its `unit_cost` from child totals:

```python
@api.depends('child_ids.total_cost', 'quantity')
def _compute_unit_cost(self):
    for rec in self:
        if not rec.child_ids:
            continue
        children_cost = sum(rec.child_ids.mapped('total_cost'))
        rec.unit_cost = children_cost / rec.quantity if rec.quantity else children_cost
```

### 3. UI Navigation Button
Provide an `action_open_sub_items` button on the Level 2 tree view to allow users to navigate directly into Level 3 with proper default context:

```python
def action_open_sub_items(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('Sub-items for %s') % (self.name or ''),
        'res_model': 'tender.boq.breakdown',
        'view_mode': 'list,form',
        'domain': [('parent_id', '=', self.id)],
        'context': {'default_parent_id': self.id, 'default_boq_line_id': self.boq_line_id.id},
    }
```

## ⚠️ Pitfalls

- **Missing `boq_line_id` on child records:** If the child only sets `parent_id`, then `tender_id` (which is related to `boq_line_id.tender_id`) will be empty, breaking default grouping by Tender in Level 3.
- **Parent BOQ line list polluted by child lines:** On `tender.boq.line`, the `breakdown_ids` One2many MUST have `domain=[('parent_id', '=', False)]` so child items do not duplicate in the Level 2 breakdown tab.

## Verification

```python
level2 = env['tender.boq.breakdown'].search([('parent_id', '=', False)])
level3 = env['tender.boq.breakdown'].search([('parent_id', '!=', False)])
print(f"Level 2: {len(level2)}, Level 3: {len(level3)}")
```
