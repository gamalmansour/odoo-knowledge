# Auto-Create and Validate Return stock.picking to Vehicle Location

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / models                               |
| Odoo Versions | 15, 16, 17, 18, 19                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.picking`, `returns`, `transit-location`, `sale.visit`, `delivery-vehicle`

---

## Problem

When a delivery representative records returns on the portal, Odoo needs to adjust inventory in addition to creating a Credit Note. If the stock return is not registered, the vehicle transit location's inventory will be out of sync. Furthermore, since portal users do not have full stock validation permissions, this must be automated securely.

## Root Cause

1. Manual inventory returns are error-prone and representatives do not have access to Odoo backend stock transfers.
2. Auto-validating stock pickings for lot-tracked products will fail if lot/serial numbers are not explicitly mapped.

## Solution ✅

Automatically generate and validate an incoming `stock.picking` from the customer location to the representative's vehicle location (Transit Location).

### 1. Identify Location and Picking Type
Use the relation chain starting from `sale.visit`:
```python
vehicle_loc = visit.plan_line_id.batch_id.delivery_vehicle_id.location_id
```

### 2. Create the Picking with lot auto-assignment
```python
picking_vals = {
    'picking_type_id': incoming_picking_type.id,
    'location_id': customer_location.id,
    'location_dest_id': vehicle_loc.id,
    'origin': f"Return from Visit: {visit.name}",
    'move_ids': [
        (0, 0, {
            'product_id': rline.product_id.id,
            'product_uom_qty': rline.qty,
            'quantity': rline.qty,
            ...
        }) for rline in visit.return_line_ids
    ]
}
picking = self.env['stock.picking'].sudo().create(picking_vals)
picking.action_confirm()
picking.action_assign()
```

### 3. Handle Lot Tracking for Incoming Returns
For lot/serial tracked products, dynamically create or assign a return lot (e.g. `RET-{visit_name}-{product}`) to avoid validation errors:
```python
for move in picking.move_ids.filtered(lambda m: m.product_id.tracking in ('lot', 'serial')):
    lot_name = f"RET-{visit.name}-{move.product_id.id}"
    lot = self.env['stock.lot'].sudo().create({
        'name': lot_name,
        'product_id': move.product_id.id,
        'company_id': visit.company_id.id
    })
    for ml in move.move_line_ids:
        ml.lot_id = lot.id
```

### 4. Validate
Use `.with_context(skip_backorder=True).button_validate()` under `sudo()` to complete the transfer automatically.

---

## ⚠️ Pitfalls

- **Circular Dependencies**: Do not override this logic in the base `sale_visit` module if the vehicle model is defined in `delivery_vehicle`. Use Odoo's class inheritance (`_inherit`) inside the dependent module.
- **Double Move Lines**: When calling `action_assign()`, Odoo might automatically create `stock.move.line` records. Do not create new ones manually if they already exist; update `lot_id` on the existing ones instead.
