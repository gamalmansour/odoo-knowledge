# Hiding Cost, Margin, and Valuation Fields via View Inheritance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟢 Low                                    |
| Last Verified | 2026-07-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `security`, `groups`, `hide_cost`, `margin`, `standard_price`, `value`

---

## Problem

> When trying to restrict visibility of sensitive financial fields (like `standard_price`, `cost`, `margin`, `value`, `remaining_value`) using view inheritance, developers often target incorrect base view XML IDs or attempt to use complex field configurations, resulting in fields still being visible or causing parse errors.

## Root Cause

> 1. Fields like `margin` are often displayed alongside percentage widgets inside `div` blocks. Simply hiding the `<field>` tag leaves labels or adjacent elements visible.
> 2. Valuation fields (`value`, `remaining_value`) in `stock.move` and `stock.quant` are scattered across specific valuation-focused tree views, not just the base form views.

## Solution ✅

> Use targeted `xpath` expressions in a custom module to apply a custom security group (e.g., `hide_cost.group_show_cost`) to the fields and their surrounding UI elements.

```xml
<!-- Example: Hiding standard_price and its UoM in product.template form -->
<xpath expr="//label[@for='standard_price']" position="attributes">
    <attribute name="groups">hide_cost.group_show_cost</attribute>
</xpath>
<xpath expr="//div[@name='standard_price_uom']" position="attributes">
    <attribute name="groups">hide_cost.group_show_cost</attribute>
</xpath>

<!-- Example: Hiding margin and margin_percent in sale.order lines -->
<!-- Hide the label and the div containing both fields -->
<xpath expr="//label[@for='margin']" position="attributes">
    <attribute name="groups">hide_cost.group_show_cost</attribute>
</xpath>
<xpath expr="//label[@for='margin']/following-sibling::div[1]" position="attributes">
    <attribute name="groups">hide_cost.group_show_cost</attribute>
</xpath>
<!-- Hide the list view columns -->
<xpath expr="//field[@name='order_line']//list//field[@name='margin']" position="attributes">
    <attribute name="groups">hide_cost.group_show_cost</attribute>
</xpath>
```

> **Target these specific views for complete coverage:**
> - `product.product_template_form_view`
> - `product.product_variant_easy_edit_view`
> - `sale_margin.sale_margin_sale_order`
> - `stock_account.stock_move_view_list_valuation`
> - `stock_account.stock_move_view_list`
> - `stock_account.product_value_form_view`
> - `stock_account.view_stock_quant_tree_inherit`

## ⚠️ Pitfalls

- **Do not** apply `groups` to the python field definition (`groups="..."`) if you want it to be configurable cleanly via UI without breaking core logic, though it is an option. Modifying views is safer for display-only restriction.
- **Do not** forget to hide the `<label>` and the wrapping `<div>` for fields like `standard_price_uom` and `margin`.

## Verification

> Install the module and verify that users without the `Show Cost` group cannot see the cost/margin fields in Product Forms, Sales Orders, and Inventory Valuation reports.

```bash
# Verify module installation without errors
./odoo-bin -c odoo19_dev.conf -u hide_cost -d odoo --stop-after-init
```

## References

- Related module: `hide_cost`
