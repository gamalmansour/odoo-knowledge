# Salla Webhook Invoice vs Order ID Mapping Pitfall

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `salla`, `webhook`, `invoice.created`, `order.created`, `order_id`, `mapping`, `ecommerce`

---

## Problem

When connecting Salla to Odoo via webhooks, orders created from `invoice.created` webhooks cannot be found in the Salla merchant orders dashboard when searched by Store Order ID, and only a fraction of store sales (e.g. 1 out of 5 orders) are ingested into Odoo.

```text
User unable to find order on Salla dashboard using Odoo store_order_id.
Missing orders from Salla because only credit card paid orders trigger invoice.created.
```

## Root Cause

1. **ID Field Misalignment:**
   In Salla's `invoice.created` payload:
   - `data['id']` is the **Invoice ID** (e.g. `812189185`).
   - `data['order_id']` is the **Salla Order ID** (e.g. `1983579617`).
   - `data['order_reference_id']` is the **Order Reference Number** (e.g. `283831366`).
   If the webhook parser reads `data.get('id')` first, it registers the invoice ID (`812189185`) as `store_id`, causing Odoo to store an ID that does not exist in the Salla Orders registry.
2. **Missing Event Subscriptions:**
   `invoice.created` only triggers when a tax invoice is issued (typically for prepaid credit card/Mada/Apple Pay orders). It does not trigger for Cash on Delivery (COD) or pending orders. The primary webhook event MUST include `order.created`.

## Solution ✅

### 1. Extract Order ID Defensively
In your webhook parser and order mapper, prioritize `order_id` and `order_reference_id` over `id` and `reference_id`:

```python
# In Salla webhook parser / FetchData:
store_id = str(data.get('order_id') or order.get('id') or '')
ref_id = str(data.get('order_reference_id') or order.get('reference_id') or store_id or '')

order_data = {
    'store_id': store_id,
    'name': ref_id,
    ...
}
```

### 2. Salla Developer Portal Configuration
Ensure the webhook endpoint in Salla Partners / Store Advanced Settings subscribes to:
- `order.created` (Essential: captures all orders regardless of payment method)
- `order.status.updated` (Captures state changes)
- `invoice.created` (Captures invoices and reconciles with existing order feeds)

## ⚠️ Pitfalls

- If both `order.created` and `invoice.created` are subscribed, ensure duplicate prevention checks `store_id` matching `order_id`. If `invoice.created` mistakenly uses `data['id']`, Odoo will create duplicate Sale Orders for the same customer purchase.
- Always provide the merchant with the direct Salla order link: `https://s.salla.sa/orders/<order_id>`.

## Verification

Send an `invoice.created` webhook payload and verify that `store_id` in `order.feed` and `channel.order.mappings` matches `data['order_id']`, not `data['id']`.
