# E-Commerce Webhook Order Feed Tax Extraction and Account Tax Fallback

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `webhook`, `ecommerce`, `salla`, `order.feed`, `taxes`, `vat`, `channel.account.mappings`, `silent-zero`

---

## Problem

When syncing e-commerce orders (e.g. Salla, Shopify, WooCommerce) into Odoo via webhook or vendor multi-channel connectors (e.g. Webkul `odoo_multi_channel_sale` / `odoo_salla_integration`), imported `sale.order` records arrive with **0.00 tax** (`amount_tax = 0.0`), even though the e-commerce store charges VAT (e.g. 15% in KSA) and the payload contains tax details.

Because orders are created without taxes:
1. `amount_total` in Odoo does not match the actual customer payment on the platform (subtotal instead of gross total).
2. Downstream customer invoices are generated without VAT, violating tax regulations (e.g. ZATCA e-invoicing Phase 2 requirements in Saudi Arabia).
3. If users manually re-add taxes, rounding errors or line reconciliation conflicts can occur.

---

## Root Cause

The defect stems from two compounding failures in vendor payload parsing and tax mapping:

### 1. Dictionary Existence Bug in Line Parsing (`fetch_data.py`)
In vendor connectors (e.g., `odoo_salla_integration/models/fetch_data.py`), order line extraction often contains code like:
```python
line_amounts = line.get('amounts') if isinstance(line.get('amounts'), dict) else {}
# BUG:
line_tax = line_amounts.get('tax') if isinstance(line_amounts, dict) else line.get('tax')
```
When `line.get('amounts')` is `None` (common in Salla webhook payloads such as `order.created` or `invoice.created`), `line_amounts` is initialized to `{}`. Because `isinstance({}, dict)` is `True`, Python evaluates `line_amounts.get('tax')`, which returns `None`, and **never evaluates the fallback** `line.get('tax')`!
In Salla's payload, tax information is located directly on `item['tax']` (or `order['tax']`), e.g.:
```json
"tax": {"percent": 15, "amount": {"amount": 25.57, "currency": "SAR"}}
```
Because the ternary condition evaluates `{}`, `line_tax` was set to `None`, resulting in an empty tax list `[]`.

### 2. Destructive Tax Wiping & Missing Auto-Mapping in `OrderFeed`
In `odoo_multi_channel_sale/models/feeds/order_feed.py`:
- `get_taxes_ids(self, taxes)` searches `channel.account.mappings` for an exact string match (e.g. `'15'` or `'Salla Tax 15%'`).
- If no mapping exists, vendor code attempts to create a dummy `account.tax` record on the fly with no account configuration, or returns `False`.
- Crucially, when `get_taxes_ids` returns `False`, `_get_order_line_vals` sets `line['tax_id'] = False`.
- In Odoo's `sale.order.line.create()`, explicitly passing `tax_id: [(6, 0, [])]` **overrides and wipes** the product's default customer taxes (`product_id.taxes_id`), forcing a 0% tax order even when the product is configured with 15% VAT!

---

## Solution ✅

### 1. Robust Tax Extraction with Multi-Level Fallback (`fetch_data.py`)
Ensure `line_tax` checks line-level dict, root line tax, order tax, and order-amounts tax:

```python
# Check line.get('tax') or line_amounts.get('tax') or order.get('tax')
line_tax = (
    line.get('tax')
    or (line_amounts.get('tax') if isinstance(line_amounts, dict) else None)
    or order.get('tax')
    or (amounts.get('tax') if isinstance(amounts, dict) else None)
)
```

For delivery / shipping lines:
```python
shipping_tax = (
    shipping_cost.get('tax')
    or order.get('tax')
    or (amounts.get('tax') if isinstance(amounts, dict) else None)
)
```

Normalize the tax identifier in `process_tax` to the numeric rate percentage (e.g. `'15%'` or `'15'`) instead of proprietary strings like `"Salla Tax 15%"`:
```python
def process_tax(self, tax, name=None):
    if not tax:
        return []
    tax_rate = str(tax.get('percent', ''))
    if not tax_rate and isinstance(tax.get('amount'), dict):
        # Calculate rate if percent is omitted
        pass
    tax_name = f"{tax_rate}%" if tax_rate and not tax_rate.endswith('%') else tax_rate
    # Return rate string for channel mapping
    return [tax_name or '15%']
```

### 2. Auto-Resolving Tax Mapping & Product Tax Fallback (`wk_feed.py`)
Override `get_taxes_ids` and `_get_order_line_vals` on `order.feed` (in your custom bridge module, e.g. `sarha_salla_webhook/models/wk_feed.py`):

```python
from odoo import api, fields, models

class OrderFeed(models.Model):
    _inherit = 'order.feed'

    def get_taxes_ids(self, taxes):
        """
        Resolve tax IDs from channel mapping or auto-match active company sale tax.
        Caches resolved tax into channel.account.mappings inside savepoint.
        """
        match = self.env['channel.account.mappings']
        tax_ids = []
        for tax in taxes:
            name = tax.strip() if isinstance(tax, str) else str(tax)
            mapping = match.search([('store_tax_value', '=', name), ('channel_id', '=', self.channel_id.id)], limit=1)
            if mapping and mapping.tax_name:
                tax_ids.append(mapping.tax_name.id)
                continue

            # Fall back to searching company active sale taxes by rate
            rate = float(name.replace('%', '').strip()) if name.replace('%', '').strip().replace('.', '', 1).isdigit() else 15.0
            found_tax = self.env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('amount', '=', rate),
                ('company_id', '=', self.channel_id.company_id.id or self.env.company.id),
            ], limit=1)

            if found_tax:
                tax_ids.append(found_tax.id)
                try:
                    with self.env.cr.savepoint():
                        match.create({
                            'store_tax_value': name,
                            'tax_name': found_tax.id,
                            'channel_id': self.channel_id.id,
                        })
                except Exception:
                    pass
        return [(6, 0, tax_ids)] if tax_ids else []

    def _get_order_line_vals(self, line, order_id):
        vals = super()._get_order_line_vals(line, order_id)
        # If line has no tax mapped, fall back to product's default customer taxes
        # NEVER pass tax_id=False when product has taxes_id configured
        if not vals.get('tax_id') or vals['tax_id'] == [(6, 0, [])]:
            product = self.env['product.product'].browse(vals.get('product_id'))
            if product and product.taxes_id:
                vals['tax_id'] = [(6, 0, product.taxes_id.ids)]
        return vals
```

### 3. Repairing Historical Draft Orders
To repair orders previously imported with 0 taxes:
```python
orders = env['sale.order'].search([('state', '=', 'draft')])
for order in orders:
    for line in order.order_line:
        if not line.tax_id:
            taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == order.company_id)
            if not taxes:
                taxes = env['account.tax'].search([
                    ('type_tax_use', '=', 'sale'),
                    ('amount', '=', 15),
                    ('company_id', '=', order.company_id.id)
                ], limit=1)
            line.tax_id = taxes
```

---

## ⚠️ Pitfalls

1. **Explicit `False` Wipes Product Defaults:**
   In Odoo, passing `tax_id: False` or `[(6, 0, [])]` in `order_line` vals prevents Odoo from falling back to `product_id.taxes_id`. If connector tax resolution returns empty, omit the key or fall back to `product_id.taxes_id`.
2. **Untracked Dummy Tax Creation:**
   Webkul's core `get_taxes_ids` attempts to create an `account.tax` if no mapping is found. Because it doesn't set `tax_group_id`, `invoice_repartition_line_ids`, or accounting accounts, posting an invoice on that tax crashes with `UserError` or breaks ZATCA e-invoicing in KSA.
3. **Draft State Mutability:**
   Only `sale.order` records in `draft` state can have their line taxes reassigned without reversing invoices or canceling stock pickings. Batch repairs must filter on `state = 'draft'`.

---

## Verification

Run the webhook unit test verifying tax extraction and feed resolution:
```bash
./odoo-bin -c sarha.conf -d sarha_live -u sarha_salla_webhook \
  --test-enable --test-tags /sarha_salla_webhook --stop-after-init
```

Ensure no draft orders remain with untaxed lines:
```python
untaxed = env['sale.order'].search([('state', '=', 'draft')]).filtered(lambda o: any(not l.tax_id for l in o.order_line))
assert len(untaxed) == 0, f"Found {len(untaxed)} orders with untaxed lines!"
```

---

## References

- Related: `orm/ecommerce-order-feed-product-automapping-and-retry.md`
- Related: `setup/zatca-warning-br-ksa-f-08-crn-scheme.md`
