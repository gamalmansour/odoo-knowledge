# Construction Seeding Pitfalls: Material Requisitions, Risk Register, and Subcontract Packages

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `seeding`, `material_requisition`, `risk`, `subcontract`, `package`, `boq`, `orm`

---

## Problem

When programmatically populating or integrating construction operational data into projects (such as seeding demo scenarios or executing unit tests), developers often encounter schema and constraint errors:

1. **Material Requisition Line Field Mismatch:**
   ```
   KeyError: 'uom_id' on 'construction.material.requisition.line'
   ```
2. **Project-Type Requisition Constraint Violation:**
   ```
   ValidationError: "In project-linked requisitions, BOQ Item is mandatory for each requisition line."
   ```
3. **Risk State Field Error:**
   ```
   ValueError: Invalid field 'state' on model 'construction.risk'
   ```
4. **Subcontract Package Bid Association:**
   Attempting to link supplier quotation lines or subcontracts incorrectly causes missing smart button badges and unlinked subcontractor agreements.

---

## Root Cause

1. **Non-Standard Field Naming (`uom` vs `uom_id`):**
   In `construction.material.requisition.line`, the Unit of Measure Many2one relation to `uom.uom` is named `uom`, not the Odoo default `uom_id`.
2. **Strict Project Requisition Cost Control:**
   When `request_type == 'project'`, model constraint `_check_boq_item_required_for_project_type` strictly demands a valid `boq_item_id` for every line. Passing null or an incompatible BOQ item triggers validation failure. Also, `requisition_type` must be `'internal'`, `'purchase'`, or `'manufacture'`.
3. **Risk Workflow Convention (`status` vs `state`):**
   `construction.risk` uses `status` (`'open'`, `'mitigating'`, `'closed'`, `'realized'`) for risk exposure lifecycle, rather than standard Odoo `state`.
4. **Subcontract Package Tender Architecture:**
   Subcontract work packages (`construction.subcontract.package`) handle multi-bid tenders using `bid_ids` (`construction.subcontract.bid`). Awarding a package requires setting `awarded_bid_id`, and the resulting agreement must link back via `awarded_subcontract_id`.

---

## Solution ✅

Follow the exact schema and relations when creating material requisitions, risks, and subcontract packages:

```python
# 1. Material Requisition with BOQ Line Allocation
requisition = env['construction.material.requisition'].create({
    'project_id': project.id,
    'request_type': 'project',
    'requisition_type': 'purchase',
    'state': 'approved',
    'line_ids': [
        (0, 0, {
            'product_id': sand_product.id,
            'description': 'Clean washed sand for basalt pavers',
            'quantity': 150.0,
            'uom': sand_product.uom_id.id,  # NOTE: 'uom', not 'uom_id'
            'estimated_unit_cost': 65.0,
            'boq_item_id': boq_item_paving.id,  # Mandatory when request_type == 'project'
        }),
    ],
})

# 2. Risk Register Entry
risk = env['construction.risk'].create({
    'project_id': project.id,
    'name': 'Marine High Tide and Wave Surges',
    'category': 'environmental',
    'probability': '4',
    'impact': '3',
    'cost_impact': 850000.0,
    'status': 'mitigating',  # NOTE: 'status', not 'state'
    'mitigation_strategy': 'Install temporary rip-rap armor before gabion placement',
})

# 3. Subcontract Package with Competitive Bids & Award
package = env['construction.subcontract.package'].create({
    'project_id': project.id,
    'name': 'Marine Works & Coastal Protection Package',
    'code': 'PKG/0002',
    'budget': 9000000.0,
    'state': 'awarded',
})

bid1 = env['construction.subcontract.bid'].create({
    'package_id': package.id,
    'subcontractor_id': marine_contractor_1.id,
    'bid_amount': 8990000.0,
    'status': 'accepted',
})

bid2 = env['construction.subcontract.bid'].create({
    'package_id': package.id,
    'subcontractor_id': marine_contractor_2.id,
    'bid_amount': 9450000.0,
    'status': 'rejected',
})

package.write({
    'awarded_bid_id': bid1.id,
    'awarded_subcontract_id': actual_subcontract.id,
})
```

---

## ⚠️ Pitfalls

- **Requisition BOQ Item Matching:** Ensure the `boq_item_id` belongs to the same `project_id` or an exception will be raised.
- **UoM Mismatch:** Using `uom_id` will silently fail or raise an unrecognized field error depending on context.
- **Risk Severity Score:** `severity_score` is computed as `int(probability) * int(impact)`; set both fields so score ranges from 1 to 25 accurately.

---

## Verification

Run verification in Odoo shell:
```python
project = env['construction.project'].browse(PROJECT_ID)
assert project.material_req_count > 0
assert project.risk_count > 0
assert project.package_count > 0
```
