# E-commerce Webhook Order Import Silent Failure & Missing SKU Auto-Mapping

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `webhook`, `ecommerce`, `order.feed`, `wk.feed`, `product-mapping`, `sku`, `silent-failure`, `salla`

---

## Problem

When receiving e-commerce webhook orders (e.g. Salla, WooCommerce, Shopify) into Multi-Channel connector architectures:
1. The webhook log marks itself as `done` or `duplicate`, but **no `sale.order` (أمر بيع) is created in Odoo**.
2. The intermediate `order.feed` record is left in `draft` or `error` with a message like:
   `No product found for order line [Product Name]` or `Product Feed Error: For product id (X) sku (Y) no mapping as well feed found`.
3. If the user clicks "Process Now" again on the webhook log, duplicate prevention logic checks `if existing_feed: return duplicate` and skips execution completely, permanently masking the failure.

```
# Error logged inside feed:
No product found for order line عطر كذا
Product Feed Error: For product id (123456) sku (SKU-001) no mapping as well feed found.
```

## Root Cause

1. **Vendor Module Mapping Assumptions:**
   Core connector modules (like Webkul `odoo_multi_channel_sale`) strictly require a pre-existing record in `channel.product.mappings` or `product.feed`. If orders arrive via webhook before full catalog synchronization, `wk.feed.get_product_id` does NOT search Odoo `product.product` by `default_code` (SKU) or `barcode` (the search lines were literally commented out in vendor code). It fails and aborts `sale.order` generation.
2. **Flawed Duplicate Detection:**
   Webhook receivers check `OrderFeed.search([('store_id', '=', store_id)])`. If an earlier failed attempt created a `draft` or `error` feed, the receiver treats it as a duplicate and skips it instead of evaluating/retrying.
3. **Mismatched Address Field Names:**
   `order.feed` uses `invoice_country_id` and `shipping_country_id` (not `_code`). Passing `_code` causes silent drops or ORM rejection.

## Solution ✅

### 1. Override `wk.feed.get_product_id` to Auto-Match Products in Odoo & Auto-Create Channel Mappings

Inherit `wk.feed` and add fallback search on `product.product` by SKU (`default_code`) and `barcode`. When matched, automatically create the `channel.product.mappings` entry:

```python
class WkFeed(models.Model):
    _inherit = 'wk.feed'

    @api.model
    def get_product_id(self, store_product_id, line_variant_ids, channel_id, default_code=None, barcode=None):
        res = super().get_product_id(store_product_id, line_variant_ids, channel_id, default_code=default_code, barcode=barcode)
        if res.get('product_id'):
            return res

        Product = self.env['product.product']
        product = False

        if default_code:
            clean_sku = str(default_code).strip()
            product = Product.search([('default_code', '=', clean_sku)], limit=1)
            if not product:
                product = Product.search([('default_code', '=ilike', clean_sku)], limit=1)

        if not product and barcode:
            product = Product.search([('barcode', '=', str(barcode).strip())], limit=1)

        if product:
            try:
                channel_id.create_product_mapping(
                    product.product_tmpl_id,
                    product,
                    store_product_id,
                    line_variant_ids or 'No Variants',
                    vals={'default_code': default_code or product.default_code, 'barcode': barcode or product.barcode}
                )
            except Exception as e:
                _logger.warning("Auto mapping failed: %s", e)
            return {'product_id': product, 'message': ''}

        return res
```

### 2. Guard Webhook Retries against Stalled Feeds

Only treat an existing feed as a duplicate if an order mapping exists AND `feed.state == 'done'`. If the feed is in `draft` or `error`, unlink old lines, write new values, and run `feed.import_items()`:

```python
order_mapping = channel.match_order_mappings(store_id)
if existing and (order_mapping or existing.state == 'done'):
    log.write({'state': 'duplicate', 'order_feed_id': existing.id})
    continue

if existing:
    existing.line_ids.unlink()
    existing.write(vals)
    feed = existing
    feed.import_items()
```

### 3. Verify `feed.state == 'done'` Before Marking Log as Processed

Never mark a webhook log as `done` unless `feed.state == 'done'`. If `feed.state == 'error'`, extract `tools.html2plaintext(feed.message)` and raise `ValueError` so the user sees the exact failure in the UI.

## ⚠️ Pitfalls

- **Unlinked Lines on Retry:** Always do `existing.line_ids.unlink()` before updating an existing feed, otherwise re-evaluation creates duplicate order lines.
- **Context Loss:** Direct calls to `feed.import_order()` bypass required context. Prefer `feed.import_items()` which runs `verify_required_fields` and `contextualize_mappings`.

## Verification

1. Post a webhook for an order whose products exist in Odoo with matching SKU but have never been synced to channel mappings.
2. Verify `sale.order` is created under Sales.
3. Check `channel.product.mappings` to confirm the automatic mapping entry was created.

## References

- Related modules: `sarha_salla_webhook`, `odoo_salla_integration`, `odoo_multi_channel_sale`
