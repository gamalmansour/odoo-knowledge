# Subcontractor Progress Invoice Unit Price and BOQ Actual Cost Confirmation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `contracts`, `subcontract`, `progress_invoice`, `actual_cost`, `work_order`, `boq`, `orm`

---

## Problem

In construction projects, developers and users observe that a BOQ item displays execution progress (e.g. 66%) while its `actual_cost` remains `0.00`:

1. **Subcontract BOQ Items:** Progress percentage reflects executed quantity, but `actual_cost` shows 0.00.
2. **Direct Execution BOQ Items:** Work orders are marked `completed` with `quantity_executed` set, but `actual_cost` remains 0.00.

---

## Root Cause

1. **Uncomputed `unit_price` on `contract.subcontractor.invoice.line`:**
   In `contract.subcontractor.invoice.line`, `unit_price` is a stored Float field with `readonly=True` (copied from the subcontract line via `action_fetch_boq()`). It is **NOT** a computed field. If an invoice line is created programmatically without explicitly passing `unit_price`, it defaults to `0.0`. Consequently:
   $$\text{current\_amount} = \text{current\_qty} \times \text{unit\_price} = \text{current\_qty} \times 0.0 = 0.0$$
   Because `project.boq.item._compute_actuals()` rolls up `subcontract_invoice_line_ids.mapped('current_amount')`, the certified cost is 0.00.
2. **Missing Cost Breakdown on Work Orders:**
   For direct items (`execution_method == 'direct'`), `_compute_actuals()` aggregates `material_target_ids`, `labor_target_ids`, and `equipment_target_ids` where `is_cost_confirmed == True`. Simply marking a work order as `completed` updates `qty_executed` and progress %, but does NOT generate actual cost unless the material issues, labor records, and equipment records are booked to the work order.

---

## Solution ✅

### 1. Ensure `unit_price` and `total_qty` on Subcontract Progress Invoices
When creating `contract.subcontractor.invoice.line` programmatically, always pass `unit_price` and `total_qty` from the subcontract BOQ line:

```python
inv_line = env['contract.subcontractor.invoice.line'].create({
    'progress_invoice_id': invoice.id,
    'boq_line_id': sub_line.id,
    'boq_item_id': boq_item.id,
    'name': sub_line.name,
    'total_qty': sub_line.qty,
    'unit_price': sub_line.unit_price,  # MANDATORY: not computed
    'current_qty': executed_qty,
})
```

### 2. Populate Resource Records on Direct Work Orders
For direct execution work orders, add the actual materials, labor, and equipment consumed:

```python
# Materials
env['project.material.issue'].create({
    'work_order_id': wo.id,
    'product_id': material_product.id,
    'quantity': 15400.0,
    'unit_cost': 850.0,
    'boq_target_id': boq_item.id,
})

# Labor
env['project.labor.record'].create({
    'work_order_id': wo.id,
    'labor_type': 'skilled',
    'count': 16,
    'hours': 320.0,
    'rate': 75.0,
    'boq_target_id': boq_item.id,
})

# Equipment
env['project.equipment.record'].create({
    'work_order_id': wo.id,
    'equipment_name': 'Vibratory Roller 12 Ton',
    'equipment_type': 'owned',
    'hours': 240.0,
    'rate': 550.0,
    'boq_target_id': boq_item.id,
})

wo._compute_total_cost()
boq_item._compute_actuals()
```

---

## ⚠️ Pitfalls

- **Do NOT assume `unit_price` is related or computed:** It is plain float; omitting it causes silent 0 financial certification.
- **`is_cost_confirmed` Trigger:** Ensure `work_order_id.state == 'completed'` so `is_cost_confirmed` evaluates to `True`, allowing cost to roll up to `project.boq.item.actual_cost`.

---

## Verification

```python
boq_item = env['project.boq.item'].browse(ITEM_ID)
assert boq_item.actual_cost > 0.0, "Actual cost must reflect certified subcontractor bills and work order costs!"
```
