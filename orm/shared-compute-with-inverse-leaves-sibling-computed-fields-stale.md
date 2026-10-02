# Shared Compute Method With Inverse Leaves Sibling Computed Fields Stale

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `inverse`, `create`, `depends`, `staleness`, `cache`

---

## Problem

When two related computed fields (such as a unit amount and a total line amount) share a single compute method, and an `inverse` is attached to only one of them:

```python
discount_amount = fields.Monetary(
    compute='_compute_discount',
    inverse='_inverse_discount_amount',
    store=True,
)
discount_total = fields.Monetary(
    compute='_compute_discount',
    store=True,
)

@api.depends('price_unit', 'discount', 'product_uom_qty')
def _compute_discount(self):
    for line in self:
        unit_discount = line.price_unit * (line.discount / 100.0)
        line.discount_amount = unit_discount
        line.discount_total = unit_discount * line.product_uom_qty

def _inverse_discount_amount(self):
    for line in self:
        line.discount = (line.discount_amount / line.price_unit) * 100.0
```

When a record is created or written with `discount_amount` provided in `vals` (e.g. `create({'discount_amount': 25.0, 'product_uom_qty': 2.0, 'price_unit': 100.0})`), the inverse correctly updates `discount = 25.0`. However, **`discount_total` remains `0.0`**:

```python
AssertionError: 0.0 != 50.0 within 2 places (50.0 difference)
```

## Root Cause

In Odoo ORM, when multiple fields share a single compute method:
1. During `create()`, the compute method runs early for `discount_total` while `discount` is still at its default `0.0`.
2. The `inverse` method runs afterwards and writes to `discount`.
3. Because `discount_amount` is already in the values/cache, Odoo's cache tracking considers the shared compute cycle already resolved or partially satisfied, and does not re-trigger `_compute_discount` for the sibling field `discount_total`.
4. As a result, `discount_total` is persisted as `0.0` instead of the expected `50.0`.

## Solution ✅

Decouple the computed fields into distinct compute methods with their own `@api.depends`, forming a clean Directed Acyclic Graph (DAG):

```python
discount_amount = fields.Monetary(
    string="Discount Amount",
    compute='_compute_discount_amount',
    inverse='_inverse_discount_amount',
    store=True,
    currency_field='currency_id',
)
discount_total = fields.Monetary(
    string="Discount Total",
    compute='_compute_discount_total',
    store=True,
    currency_field='currency_id',
)

@api.depends('price_unit', 'discount')
def _compute_discount_amount(self) -> None:
    for line in self:
        if line.display_type or not line.product_id:
            line.discount_amount = 0.0
            continue
        discount_pct = (line.discount or 0.0) / 100.0
        line.discount_amount = line.price_unit * discount_pct

@api.depends('discount_amount', 'product_uom_qty')
def _compute_discount_total(self) -> None:
    for line in self:
        if line.display_type or not line.product_id:
            line.discount_total = 0.0
            continue
        line.discount_total = line.discount_amount * line.product_uom_qty

def _inverse_discount_amount(self) -> None:
    for line in self:
        if line.display_type or not line.product_id:
            continue
        if line.price_unit:
            line.discount = (line.discount_amount / line.price_unit) * 100.0
        else:
            line.discount = 0.0
        # Defensively update total line discount immediately
        line.discount_total = line.discount_amount * line.product_uom_qty
```

## ⚠️ Pitfalls

- **`digits` attribute on `fields.Monetary`:** Do NOT specify `digits='Product Price'` on a `fields.Monetary`. `Monetary` precision is governed by `currency_field` (usually `currency_id`). Passing `digits` triggers an unknown parameter warning in Odoo 17+.
- **Zero price safeguard:** Always guard against division by zero in `_inverse_discount_amount` when `price_unit == 0.0`.
- **Section and Note lines (`display_type`):** In `sale.order.line`, section and note lines have no `product_id`. Explicitly zero out discounts for them to prevent calculations or crashes.

## Verification

Run the unit test suite covering both forward percentage calculation and inverse monetary amount assignment:

```bash
odoo-bin -c odoo17_dev.conf -d <db> -u <module> --test-enable --test-tags /<module> --stop-after-init
# Expected: 0 failed, 0 error(s)
```

## References

- Related file: `orm/stored-compute-incomplete-depends-silent-staleness.md`
- Related file: `orm/onchange-only-computation-breaks-nonform-create.md`
