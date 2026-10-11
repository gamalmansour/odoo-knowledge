# E-Commerce Webhook Fail-Closed Secret Enforcement Disables Live Store Subscriptions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `webhook`, `security`, `salla`, `ecommerce`, `hmac`, `fail-closed`, `outage`, `401`

---

## Problem

After deploying an update to an e-commerce webhook controller (e.g. Salla, Shopify, WooCommerce) enforcing strict HMAC signature verification, orders abruptly stop arriving in Odoo. In the server logs:

```text
WARNING sarha_live odoo.addons.sarha_salla_webhook.controllers.main: Salla webhook rejected: signature mismatch from 18.157.156.218 (strategy=None)
INFO sarha_live werkzeug: 18.157.156.218 - - [04/Oct/2026 12:00:00] "POST /salla/webhook/order HTTP/1.1" 401 - 8 0.003 0.010
```

Furthermore, the external e-commerce platform (e.g., Salla) receives consecutive HTTP 401 Unauthorized responses, retries up to its failure threshold, and automatically deactivates/suspends the webhook subscription on the merchant dashboard. In Odoo, zero orders are created, and zero logs enter the webhook log table because the request is rejected before payload recording.

---

## Root Cause

A developer attempts to enforce "fail-closed" security by requiring a webhook secret:

```python
# BUGGY CONTROLLER IMPLEMENTATION:
matched = Channel
for channel in channels:
    if channel.salla_webhook_secret:
        if self._signature_is_valid(channel.salla_webhook_secret, raw_body, received_sig):
            matched = channel
            break
        if headers.get('X-Salla-Secret') == channel.salla_webhook_secret:
            matched = channel
            break
    # Missing unconfigured secret fallback!

if not matched:
    return self._json_response(401, {'status': 'unauthorized'})
```

In production, the channel record in the database (`multi.channel.sale`) was created without a configured webhook secret (`salla_webhook_secret` is `False` / NULL / empty string). 
Because `channel.salla_webhook_secret` evaluates to `False`:
1. The verification loop skips without matching.
2. `matched` remains empty.
3. Every single legitimate order webhook from the store is rejected with HTTP 401.
4. The merchant dashboard in Salla marks the webhook as failed and deactivates it.

---

## Solution ✅

Implement a two-pass matching strategy that guarantees:
1. **Strict HMAC Security** when a secret IS configured on the channel.
2. **Graceful Fallback / Direct Reception** when the channel has not yet configured a secret, avoiding store paralysis.

### 1. Two-Pass Controller Verification

```python
matched = Channel
signature_ok = False

# Pass 1: Match channels with configured secret against HMAC signature or secret header
for channel in channels:
    if channel.salla_webhook_secret:
        if self._signature_is_valid(channel.salla_webhook_secret, raw_body, received_sig):
            matched = channel
            signature_ok = True
            break
        if headers.get('X-Salla-Secret') == channel.salla_webhook_secret:
            matched = channel
            signature_ok = True
            break

# Pass 2: Fallback to channels without configured secret (unverified development / open mode)
if not matched:
    for channel in channels:
        if not channel.salla_webhook_secret:
            matched = channel
            signature_ok = True
            _logger.info(
                'Salla webhook accepted for channel %s in unverified mode (no webhook secret configured).',
                channel.name,
            )
            break

# Reject if no channel matched (e.g. secret was configured but signature failed)
if not matched:
    _logger.warning(
        'Salla webhook rejected: signature mismatch from %s (strategy=%s)',
        remote_addr, headers.get(HDR_STRATEGY))
    return self._json_response(401, {'status': 'unauthorized'})
```

### 2. Salla Dashboard Reactivation Procedure

When an outage occurs:
1. Open Salla Merchant Dashboard: `إعدادات المتجر -> الإعدادات المتقدمة -> Webhooks`.
2. Inspect the webhook status. If marked as failed or disabled, re-enable it and click "فحص / اختبار" (Test).
3. Under webhook history / events, click "إعادة إرسال" (Resend) for all missed orders during the outage period.
4. Copy the Webhook Secret from Salla and paste it into Odoo under `Multi-Channel -> Salla -> Webhook Secret` to enable full HMAC-SHA256 signature verification.

---

## ⚠️ Pitfalls

- **Do NOT confuse "no hardcoded secret shipped in code" with "reject unconfigured channels in production".** Shipped default secrets in XML/data files are vulnerabilities; but breaking unconfigured client channels without a migration or admin warning causes instant operational downtime.
- **Unit test trap:** Writing a unit test asserting `test_channel_without_secret_accepts_nothing -> 401` codifies the outage into CI. Unit tests should assert that an unconfigured channel accepts requests (200 OK) while a configured channel strictly rejects bad/missing signatures.
- **External auto-deactivation:** Fixing the Odoo code alone does NOT resume order flow if the third-party provider (Salla, Shopify) auto-suspended the webhook endpoint after repeated 401 errors. Always instruct the user to verify provider dashboard status.

---

## Verification

```bash
# 1. Run unit tests for both configured and unconfigured channels
./odoo-bin -c sarha.conf -d sarha_live -u sarha_salla_webhook \
  --test-enable --test-tags /sarha_salla_webhook --stop-after-init
# -> 0 failed, 0 error(s)

# 2. Check channel in DB
psql sarha_live -c "SELECT id, name, salla_webhook_secret FROM multi_channel_sale;"
```

---

## References

- Related file: `security/shipped-secret-default-plus-active-dev-gateway-is-a-payment-bypass.md`
- Related file: `orm/ecommerce-webhook-tax-extraction-and-fallback.md`
- Related file: `misc/polymorphic-ecommerce-webhook-payload-type-guards.md`
