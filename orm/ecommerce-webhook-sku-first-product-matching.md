# E-Commerce Webhook Order Feed: Prioritizing Exact SKU Over Generic Template Mappings

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `webhook`, `ecommerce`, `salla`, `order.feed`, `sku`, `default_code`, `product.product`, `channel.product.mappings`, `variant-mismatch`

---

## Problem

When syncing e-commerce orders (e.g. Salla, Zid, Shopify) via webhooks or multi-channel integration modules (such as `odoo_multi_channel_sale` / `odoo_salla_integration`), orders containing variable products (e.g. Perfume 100ml, Oud 100g) are imported into Odoo with the **wrong product variant** (e.g. Oud 12g instead of Oud 100g), even though the incoming payload explicitly specifies the correct variant SKU (`default_code = "11111537"`).

### Consequences
1. **Warehouse Picking Errors:** Warehouse staff fulfill and dispatch the wrong item (e.g., shipping a 12g bottle instead of a 100g bottle, or vice-versa), resulting in customer complaints, returns, and inventory discrepancies.
2. **Pricing and Inventory Distortion:** Stock is decremented from the wrong `product.product` record, corrupting physical inventory counts and cost of goods sold (COGS).
3. **Silent Failure:** The order imports successfully without errors (`state = 'done'`), making the mismatch difficult to catch until physical shipment or audit.

---

## Root Cause

In multi-channel connectors (like Webkul's `odoo_multi_channel_sale`), the default resolution in `feed.py:get_product_id` matches on `(store_product_id, line_variant_ids)`:

```python
# odoo_multi_channel_sale/models/feeds/feed.py
match = self._context.get('variant_mappings').get(channel_id.id, {}).get(store_product_id, {}).get(line_variant_ids)
if match:
    match = self.env['channel.product.mappings'].browse(match)
    product_id = match.product_name
```

### Why it fails:
1. **Template vs Variant Store IDs:** In platforms like Salla, the incoming line often provides the parent product ID (e.g., `1052040504`) in `product_id`. If `line_variant_ids` is empty or defaults to `'No Variants'`, the connector looks up the mapping table `channel_product_mappings`.
2. **Stale/First-Variant Mapping:** An existing mapping record often binds `(store_product_id = '1052040504', store_variant_id = 'No Variants')` to whatever variant was imported first (e.g., product `481` - 12g).
3. **Execution Order Inversion:** If `super().get_product_id(...)` is invoked **before** inspecting `default_code` (SKU), the method immediately returns the cached, wrong variant, completely bypassing the incoming SKU (`11111537`).

---

## Solution ✅

Enforce a **Strict Priority Hierarchy** in the feed's product resolution:
1. **Step 1 — Exact SKU (Internal Reference / `default_code`):** If the incoming item specifies a SKU, search `product.product` directly by `default_code`. An exact SKU match is uniquely definitive for a sellable inventory variant.
2. **Step 2 — Exact Barcode:** If SKU is absent, check barcode.
3. **Step 3 — Standard Channel Mapping (`super()`):** Fall back to channel mapping only if SKU/Barcode did not yield a direct match.
4. **Step 4 — Fallback & Auto-Creation:** If still unmatched, evaluate fallback name matching or auto-create.
5. **Step 5 — Self-Healing Mapping:** When an exact SKU is matched, register/update the `channel.product.mappings` record with the specific variant.

### Implementation in `wk.feed` / `order.feed`

```python
# -*- coding: utf-8 -*-
from odoo import api, fields, models

class WkFeed(models.Model):
    _inherit = 'wk.feed'

    @api.model
    def get_product_id(self, store_product_id, line_variant_ids, channel_id, default_code=None, barcode=None, **kwargs):
        """Override get_product_id:
        Prioritize exact SKU match BEFORE consulting generic template mappings.
        """
        line_name = kwargs.get('line_name') or self._context.get('current_line_name')
        product = False
        Product = self.env['product.product']

        # 1. المطابقة عبر رمز الـ SKU (default_code) أولاً لضمان مطابقة المتغير (Variant) الدقيق
        if default_code:
            clean_sku = str(default_code).strip()
            if clean_sku:
                product = Product.search([('default_code', '=', clean_sku)], limit=1)
                if not product:
                    product = Product.search([('default_code', '=ilike', clean_sku)], limit=1)

        # 2. المطابقة عبر الباركود (Barcode) ثانياً
        if not product and barcode:
            clean_barcode = str(barcode).strip()
            if clean_barcode:
                product = Product.search([('barcode', '=', clean_barcode)], limit=1)

        # 3. محاولة المطابقة القياسية من جداول الربط الأصلية إن لم نجد بالـ SKU أو الباركود
        if not product:
            res = super().get_product_id(
                store_product_id, line_variant_ids, channel_id, default_code=default_code, barcode=barcode
            )
            if res.get('product_id'):
                return res

        # 4. المطابقة عبر معرف المتجر إذا تم استخدامه كرمز
        if not product and store_product_id:
            clean_id = str(store_product_id).strip()
            if clean_id:
                product = Product.search(['|', ('default_code', '=', clean_id), ('barcode', '=', clean_id)], limit=1)

        # 5. المطابقة بالاسم الصريح كخيار بديل
        if not product and line_name:
            clean_name = line_name.strip()
            product = Product.search([('name', '=', clean_name)], limit=1)
            if not product:
                product = Product.search([('name', '=ilike', clean_name)], limit=1)

        # 6. تحديث جدول الربط ذاتياً لضمان اتساق العمليات المستقبلية
        if product:
            store_prod_str = str(store_product_id or product.id)
            variant_str = line_variant_ids or 'No Variants'
            existing_mapping = self.env['channel.product.mappings'].search([
                ('channel_id', '=', channel_id.id),
                ('store_product_id', '=', store_prod_str),
                ('store_variant_id', '=', variant_str),
            ], limit=1)
            if not existing_mapping:
                try:
                    with self.env.cr.savepoint():
                        channel_id.create_product_mapping(
                            product.product_tmpl_id,
                            product,
                            store_prod_str,
                            variant_str,
                            vals={'default_code': default_code or product.default_code, 'barcode': barcode or product.barcode}
                        )
                except Exception:
                    pass

            return {'product_id': product, 'message': ''}

        return super().get_product_id(
            store_product_id, line_variant_ids, channel_id, default_code=default_code, barcode=barcode
        )
```

---

## ⚠️ Pitfalls

1. **Blindly Trusting `store_product_id` Mappings:** E-commerce platforms frequently pass the Parent/Template ID as the line's `product_id`. Relying on `channel_product_mappings` without checking SKU leads to linking all variants to whichever variant was mapped first.
2. **Duplicate SKUs in Odoo:** Ensure database uniqueness on `default_code` across active products (`active = True`). If duplicate SKUs exist, `limit=1` returns an arbitrary record.
3. **Case Sensitivity:** Use `=ilike` as a fallback if the merchant platform normalizes or alters SKU casing (e.g. `sku-100g` vs `SKU-100G`).

---

## Verification

To verify that SKU takes precedence over stale channel mappings:
1. Find a product template with multiple variants (e.g. 12g SKU `11111538` and 100g SKU `11111537`).
2. Deliberately map the parent store ID to the 12g variant in `channel_product_mappings`.
3. Process an order feed line with `store_product_id = parent_id` and `line_product_default_code = '11111537'`.
4. Verify that `get_product_id` resolves to the 100g variant (ID matching SKU `11111537`), proving the stale template mapping was superseded.

---

## References

- Related: `orm/ecommerce-webhook-tax-extraction-and-fallback.md`
- Module: `sarha_salla_webhook/models/wk_feed.py`
- Core Connector: `odoo_multi_channel_sale/models/feeds/feed.py`
