# Odoo 19 Upgrade: stock.valuation.layer to product.value

## Overview
In Odoo 19, the `stock.valuation.layer` model has been extensively refactored/removed in favor of `product.value` and different valuation mechanisms within `stock_account`.

## Context & Problem
When upgrading inventory or accounting modules to Odoo 19, references to `stock.valuation.layer` in Python models, wizard logic, or XML views will cause `ParseError` or `KeyError` during upgrade. 
Similarly, certain report views for valuation have been removed or replaced, causing invalid inheritance (`inherit_id`).

## Solution ✅
- **Python Models:** Rename inheritance or calls from `stock.valuation.layer` to `product.value` or the appropriate new model in `stock_account`.
- **Method Signatures:** Check methods like `_prepare_` functions in `stock.move` which have changed signatures (e.g. `_prepare_account_move_vals` takes different kwargs).
- **XML Views:** Remove `<record>` definitions that inherit from deprecated views like `stock.view_valuation_layer_tree`. Validate inherited views exist in Odoo 19.

## ⚠️ Pitfalls
- Leaving `<button name="action_delete_duplicates" ...>` inside inherited views. This action was removed in Odoo 19, causing a `ParseError` when the view parses.
- Assuming `product.value` has the exact same fields as `stock.valuation.layer`. Review `product.value` definition in `addons/stock_account/models/product_value.py`.

**Last Verified:** Odoo 19.0 (July 2026)
