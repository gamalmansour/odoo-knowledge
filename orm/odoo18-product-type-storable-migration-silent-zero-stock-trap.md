# Odoo 18 Product Type Storable Migration: Deprecation of type == 'product' Causes Silent Zero On-Hand Stock

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `odoo18`, `is_storable`, `product_type`, `stock`, `free_qty`, `on_hand`, `migration`

---

## Problem

In Odoo 18, custom models, smart buttons, or routing logic checking on-hand or free inventory via `product.type == 'product'` silently fail. The condition evaluates to `False`, forcing computed stock quantities to zero (`0.0`), even when products have ample stock in the warehouse.

In material requisitions, replenishment wizards, and dispatch workflows, this causes buttons like `Check Stock & Route` or automated transfers to falsely report:
```
UserError: Nothing to route: every line is empty, or already fully transferred to the destination / ordered on an existing purchase order.
```
Site engineers and storekeepers cannot transfer newly received inventory from the main warehouse to project sites because the system thinks on-hand stock is `0.0`.

## Root Cause

1. Prior to Odoo 18, storable tracked inventory was identified by `product.type == 'product'`, while consumables had `type == 'consu'` and services had `type == 'service'`.
2. In Odoo 18, Odoo refactored product types:
   - Storable products now have `type == 'consu'` combined with `is_storable = True`.
   - The selection option `'product'` in `product.template.type` was completely removed from core.
3. Any legacy check using `if product.type == 'product':` will **silently evaluate to False** in Odoo 18 for all storable products.
4. As a result, logic calculating `qty_on_hand`, `free_qty`, or stock availability falls into the fallback branch (`on_hand = 0.0`), blocking internal transfers and stock reservations.

## Solution ✅

Use version-compatible inspection supporting both Odoo 18+ (`is_storable`) and pre-18 (`type == 'product'`):

```python
# Multi-version safe check for storable products:
is_storable = getattr(product, 'is_storable', False) or (product and product.type == 'product')

if product and is_storable and location:
    on_hand = product.with_context(location=location.id).free_qty
else:
    on_hand = 0.0
```

### Applied Pattern in Model Computes

```python
class MaterialRequisitionLine(models.Model):
    _inherit = 'construction.material.requisition.line'

    @api.depends('product_id', 'qty', 'requisition_id.location_id')
    def _compute_stock(self):
        for line in self:
            loc = line.requisition_id.location_id
            product = line.product_id
            is_storable = getattr(product, 'is_storable', False) or (product and product.type == 'product')
            if product and is_storable and loc:
                on_hand = product.with_context(location=loc.id).free_qty
            else:
                on_hand = 0.0
            line.qty_on_hand = on_hand
            line.shortfall_qty = max(line.qty - on_hand, 0.0)
```

## ⚠️ Pitfalls

- **Do NOT write `product.type == 'consu'` to check for inventory tracking**: Consumables without stock tracking also have `type == 'consu'`, but have `is_storable = False`. Checking only `type == 'consu'` will attempt to check quants and create transfers for non-tracked consumable goods.
- **Do NOT assume `is_storable` exists on older Odoo databases**: In Odoo 16/17, `product` does not have the `is_storable` field. Always use `getattr(product, 'is_storable', False)` to ensure backwards compatibility across shared custom addons.

## Verification

1. In Odoo 18 shell, inspect a known storable product:
   ```python
   p = env['product.product'].browse(product_id)
   print(p.type)         # 'consu'
   print(p.is_storable)   # True
   ```
2. Trigger the requisition stock route:
   ```python
   req = env['construction.material.requisition'].search([('name', '=', 'MR/2026/00072')])
   req.action_smart_route()
   # Successfully creates stock.picking (Internal Transfer) from main store to project site
   ```

## References

- Odoo Core 18.0 commit: `addons/stock/models/product.py` (`is_storable` introduction)
- Related module: `construction_requisition_stock/models/requisition_stock.py`
