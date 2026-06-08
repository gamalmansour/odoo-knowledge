# 📝 sale_stock_margin overriding purchase_price

**Category**: ORM / Computes
**Tags**: #sale_margin #sale_stock_margin #purchase_price #override
**Odoo Versions**: All (15+)

## ❌ Problem / Symptom
When you have a custom module that calculates the `purchase_price` (Cost) on a sale order line based on a specific logic (like taking the cost from a selected Lot/Serial), you might notice that **when the Sale Order is confirmed, the cost magically resets to the product's standard cost**.

This happens because the standard Odoo module `sale_stock_margin` overrides `_compute_purchase_price` with dependencies on `move_ids` and `picking_id.state`. When the SO is confirmed, moves are created, triggering the compute. `sale_stock_margin` then calculates the average price from the moves and **overwrites** your custom price without calling `super()` for those lines.

## ✅ Solution
1. Add `sale_stock_margin` to your custom module's `depends` list in `__manifest__.py` so your module always loads AFTER it.
2. In your overridden `_compute_purchase_price`, make sure to call `super()._compute_purchase_price()` first to let standard Odoo logic execute (which handles products without your custom condition).
3. Then, loop through `self` and re-apply your custom logic (e.g., forcing the lot's cost) so it overwrites Odoo's standard calculated cost.
