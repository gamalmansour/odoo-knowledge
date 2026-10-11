# Odoo 17+ Global Discount Wizard Negative Lines Ignored in Custom Discount Aggregations

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `sale`, `discount`, `sale_order_discount`, `wizard`, `negative-lines`, `aggregation`, `is_downpayment`

---

## Problem

In Odoo 17+, the standard Sales module introduces the Discount Wizard (`sale.order.discount`) triggered by the "Discount" button below order lines.

When an operator applies:
1. **Global Discount (`so_discount`)**: a percentage on the whole order.
2. **Fixed Amount (`amount`)**: a fixed cash reduction on the order.

Odoo does **not** populate the `discount` percentage field on individual lines. Instead, it generates a dedicated `sale.order.line` with:
- `product_id`: `company_id.sale_discount_product_id` (a service product created on the fly).
- `price_unit`: negative value (e.g. `-50.0`).
- `discount`: `0.0`.

Any custom aggregate field on `sale.order` (such as `amount_discount` or total discount tracking) that computes the total discount purely from line-level discount percentages or `discount_total` (`price_unit * discount% * qty`) **silently evaluates to 0.0 for global discounts**, omitting hundreds or thousands in price reductions from management summaries, reporting, and printed header totals.

## Root Cause

Custom implementations typically sum line discount fields:

```python
# BROKEN: ignores global discount lines created by the Odoo 17 wizard
@api.depends('order_line.discount_total')
def _compute_amount_discount(self):
    for order in self:
        order.amount_discount = sum(line.discount_total for line in order.order_line)
```

Because Odoo's global discount lines carry `discount = 0.0` and a negative `price_unit`, `line.discount_total` on those lines is `0.0`. The order-level field remains blind to global discounts.

## Solution ✅

Aggregate both line discounts from positive product lines AND the magnitude of dedicated global discount lines, while strictly shielding against down payments and section/note lines:

```python
@api.depends(
    'order_line.discount_total',
    'order_line.price_unit',
    'order_line.product_uom_qty',
    'order_line.product_id',
    'order_line.is_downpayment',
    'order_line.display_type',
    'company_id.sale_discount_product_id',
)
def _compute_amount_discount(self) -> None:
    for order in self:
        total_discount = 0.0
        discount_product = order.company_id.sale_discount_product_id

        for line in order.order_line:
            # Safeguard 1: Ignore section headers, notes, and advance down payments
            if line.display_type or line.is_downpayment:
                continue

            # Safeguard 2: Catch global discount lines (negative unit price or discount product)
            if line.price_unit < 0 or (discount_product and line.product_id == discount_product):
                total_discount += abs(line.price_unit * line.product_uom_qty)
            else:
                # Standard line-level discount
                total_discount += line.discount_total

        order.amount_discount = total_discount
```

## ⚠️ Pitfalls

- **Do NOT mistake Down Payments for Discounts:** In standard Odoo, down payments also produce negative line deductions upon final invoice creation, but with `line.is_downpayment = True`. Never blindly sum all negative lines without checking `not line.is_downpayment`.
- **Multiple Tax Groups:** When the order has items with different tax rates (e.g. 15% and 0%), Odoo's wizard generates multiple discount lines (one per tax group). The aggregation loop handles multiple negative lines naturally.
- **Line Tree View Cleanliness:** On global discount lines (`price_unit < 0`), defensively clamp `discount_amount` and `discount_total` to `0.00` to prevent redundant or confusing positive discount amounts displayed next to negative unit prices in the tree view.

## Verification

Add unit tests asserting that:
1. Adding a negative price line or `sale_discount_product_id` line increments `order.amount_discount`.
2. Setting `is_downpayment=True` on a negative line does NOT increment `amount_discount`.
3. Combining line discounts and global discount lines yields their exact mathematical sum.

```bash
./odoo-bin -c odoo17_dev.conf -d <db> -u <module> --test-enable --test-tags /<module> --stop-after-init
```
