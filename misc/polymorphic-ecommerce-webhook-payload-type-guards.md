# Polymorphic E-Commerce Webhook Payload Type Guards ('str' object has no attribute 'get')

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `webhook`, `salla`, `ecommerce`, `integration`, `payload`, `json`, `type-error`

---

## Problem

When receiving and processing external e-commerce webhooks (such as Salla, Shopify, WooCommerce, or Magento) into Odoo feed records (`order.feed`, `sale.order`), processing crashes with:

```
AttributeError: 'str' object has no attribute 'get'
```
or:
```
AttributeError: 'float' object has no attribute 'get'
```

This marks the incoming webhook log with `state='error'` and prevents the sale order and inventory reservations from being created in Odoo.

## Root Cause

Connectors (e.g. Webkul `FetchData`) frequently hardcode unsafe nested `.get()` chains assuming every field is a dictionary:

1. **Dates:** Calling `order.get('date').get('date')`. When Salla or other platforms send ISO timestamps or MySQL datetime strings (`"2026-09-07 10:15:00"`), `order.get('date')` is a `str`, causing `'str' object has no attribute 'get'`.
2. **Order Status:** Calling `order.get('status').get('slug')`. In many events or API versions, `status` is sent as a plain string slug (`"under_review"` or `"completed"`).
3. **Amounts & Taxes:** Calling `amounts.get('shipping_cost').get('amount')` or `tax.get('amount').get('amount')`. Often `shipping_cost` or `tax` is sent as a scalar float or numeric string (`25.0` or `"15.00"`).
4. **Addresses & Shipments:** Calling `order.get('shipments')[0].get('ship_to').get('name')` where shipments is a list of strings or `ship_to` is a plain text string.

## Solution ✅

### 1. Robust Universal Scalar & Nested Amount Extractor
Implement a recursive extraction helper that gracefully accepts `float`, `int`, `str` (with commas/whitespace), and nested dictionaries (`{'amount': ...}`, `{'total': ...}`):

```python
def _get_amount(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(',', '').strip())
        except (ValueError, TypeError):
            return default
    if isinstance(val, dict):
        for key in ('amount', 'total', 'value'):
            if key in val and val[key] is not None:
                return _get_amount(val[key], default)
    return default
```

### 2. Polymorphic Type-Guarded Date & Status Extraction
Extract dates and states handling both string and dictionary payloads, with string normalization for Odoo:

```python
# Date
order_date = order.get('date')
if isinstance(order_date, dict):
    date_order = order_date.get('date')
elif isinstance(order_date, str):
    date_order = order_date
else:
    date_order = order.get('created_at') or fields.Datetime.now()

if isinstance(date_order, str):
    date_order = date_order.replace('T', ' ').split('+')[0].replace('Z', '').strip()[:19]

# Status
order_status = order.get('status')
if isinstance(order_status, dict):
    order_state = order_status.get('slug') or order_status.get('name') or 'new'
elif isinstance(order_status, str):
    order_state = order_status
else:
    order_state = 'new'
```

### 3. Surface Full Traceback in Webhook Log Model
Never swallow or truncate exceptions to single-line `str(exc)`. Always log `traceback.format_exc()`:

```python
except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    _logger.exception('Webhook processing failed: %s', exc)
    log.write({
        'state': 'error',
        'error_message': f"{str(exc)}\n\n{tb}",
    })
```

## ⚠️ Pitfalls

- **Payload Version Drift:** E-commerce platforms regularly update webhook schemas between V1, V2, and sub-versions without warning. Never assume a fixed schema for webhook payloads.
- **Invoice vs Order Webhooks:** For invoice events (`order.invoice`), the order details may be nested under `data['order']`, or direct fields on `data` (like `data['order_id']`). Always inspect and merge both objects.
- **Idempotency:** Always verify whether an `order.feed` already exists for `(channel_id, store_id)` before calling processing logic to avoid duplicate orders from webhook retries.

## Verification

Run the unit test simulating scalar and string payloads:

```bash
python3 -m unittest sarha_salla_webhook.tests.test_salla_webhook
```

## References

- Related modules: `odoo_salla_integration`, `sarha_salla_webhook`
