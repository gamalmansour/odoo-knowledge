# Writable `related=` (`readonly=False`) on Transaction Lines Triggers Parent Master-Data `AccessError`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19 (All)                   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `related`, `readonly`, `AccessError`, `sale.order.line`, `product.product`, `security`

---

## Problem

> A boolean or configuration flag on a transaction line (e.g., `sale.order.line.is_course`) is defined as `related='product_id.is_course', readonly=False` so that quotations using a generic service product can still mark individual lines as course lines. Tests running as `admin` (superuser) pass 100%, but when a real salesperson (`sales_team.group_sale_salesman` without `product` write rights) creates or confirms a quotation line, Odoo crashes with `AccessError`:

```
odoo.exceptions.AccessError: You are not allowed to modify 'Product Variant' (product.product) records.
This operation is allowed for the following groups:
    - Sales/Administrator
```

## Root Cause

> In Odoo's ORM (`odoo/fields.py`), setting `readonly=False` on a `related=` field registers `_inverse_related` as the field's inverse method. Whenever `is_course` is included in `vals` during `sale.order.line.create()` or `write()` (including form view submission or CRM-to-Quotation context defaults), Odoo executes `_inverse_related` as the **current user** (`su=False`) and attempts to write `vals['is_course']` back onto `line.product_id` (`product.product`). Ordinary salespersons have `read` access to `product.product`, never `write` access — causing an immediate `AccessError` AND risking accidental mutation of shared master-data products!

## Solution ✅

> Replace `related='product_id.is_course', readonly=False` with a stored, editable computed field (`store=True, readonly=False, precompute=True`). Odoo computes the default from `product_id` / `course_id` on line creation or product change, allows per-line overrides in `vals` without touching `product.product`, and never triggers `_inverse_related`:

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_course = fields.Boolean(
        string="Is Course Offering",
        compute='_compute_is_course',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('product_id', 'course_id')
    def _compute_is_course(self) -> None:
        for line in self:
            line.is_course = bool(line.course_id or line.product_id.is_course)
```

## ⚠️ Pitfalls

- **Never rely on superuser `TransactionCase` alone:** Superuser (`env.su=True`) bypasses `ir.model.access` on `product.product`, hiding the `_inverse_related` write completely. Always test `sale.order` / `account.move` / `purchase.order` line creation with `.with_user(restricted_sales_user)`.
- **Data corruption hazard even for admins:** When a Sales Administrator overrides a `related(..., readonly=False)` flag on a single quotation line using a shared fallback service product (e.g., `TRN-SRV`), `_inverse_related` mutates the master `product.product` record globally for all future orders!
- **Type='json' controller `jsonrequest` trap (bonus check):** In Odoo 17 `type='json'` webhooks, `request.dispatcher.jsonrequest` holds the outer JSON-RPC 2.0 envelope (`{"jsonrpc": "2.0", "params": {...}}`), whereas `**kw` holds the unpacked `params`. Always unwrap `raw_json.get('params')` before whitelisting payload keys.

## Verification

```bash
/Users/gamal/odoo/odoo17.0/.venv/bin/python3 /Users/gamal/odoo/odoo17.0/odoo-bin \
  -d test_db --test-enable --test-tags /openeducat_ghtc:TestSalesBatchCreation.test_16_salesperson_confirm_course_so_creates_batch_and_logistics --stop-after-init
```

## References

- Related file: `security/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `orm/required-stored-compute-needs-no-default-and-no-required.md`
