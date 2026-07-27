# Invoice Shows "Paid" on First Confirm with No Payment — Zombie Invoice from a Swallowed Create Error

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / account                              |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `account.move`, `payment_state`, `paid`, `savepoint`, `except`, `zombie-record`, `payment_term`, `translate`, `formataddr`, `money-integrity`

---

## Problem

Confirming a customer invoice instantly flips it to **"Paid"** although no payment or reconciliation exists. Resetting it to draft and confirming again behaves normally ("Posted / Not Paid"). Symptom is systematic for invoices auto-created by a custom flow, never for manually created ones.

## Root Cause

Three stacked defects:

1. **Trigger — jsonb name crashes core mail SQL path:** a custom module redefined `res.partner.name` with `translate=True` (column becomes JSONB). Core mail (`mail.followers._get_recipient_data`) reads partner names via **raw SQL**, gets a Python `dict` instead of `str`, and `formataddr()` raises `AttributeError: 'dict' object has no attribute 'encode'` during the notification that runs INSIDE invoice creation.

2. **Enabler — `except Exception` without a savepoint:** the auto-invoice hook did:
```python
try:
    invoices = order.sudo()._create_invoices()
except Exception as error:
    order.message_post(body=_("Automatic invoicing failed: %s", error))
    continue
```
Catching the error without a savepoint keeps everything `_create_invoices` had already flushed — a **zombie draft invoice**: product lines present (with zero amounts), **no `payment_term` receivable line**.

3. **Detonator — core payment_state semantics:** `account.move.amount_residual` sums residuals of `display_type == 'payment_term'` lines ONLY. A move with no such line has residual 0, and `_compute_payment_state` maps zero-residual to **`paid`** even with zero reconciliations. The zombie is "balanced" (all zeros), so `action_post()` succeeds → instant fake "Paid".

Why re-confirm works: reset-to-draft + post re-runs the full dynamic-lines sync, which rebuilds the receivable/payment-term line correctly → real residual → "Not Paid".

## Solution ✅

Wrap the risky create in a savepoint so a failure removes the partial record entirely (the outer catch still protects the sale confirmation):

```python
try:
    with self.env.cr.savepoint():
        invoices = order.sudo()._create_invoices()
except Exception as error:  # never block the sale on a billing issue
    _logger.warning("Auto-invoice failed for sale order %s: %s", order.name, error)
    order.message_post(body=_("Automatic invoicing failed: %s", error))
    continue
```

Verified end-to-end: before the fix the repro leaves a zombie that posts as `paid`; after the fix the same crash leaves `invoice_ids` empty and the order confirmed.

Also address the TRIGGER separately — `translate=True` on `res.partner.name` must go (see [translated_many2one_search](translated_many2one_search.md) for the safe alternative: a separate Arabic name field + `_rec_names_search`).

## ⚠️ Pitfalls

- **Detection on existing DBs:** hunt for zombies already posted as fake-paid:
```sql
SELECT m.id, m.name, m.amount_total FROM account_move m
WHERE m.move_type IN ('out_invoice','out_refund') AND m.state='posted'
  AND m.payment_state='paid'
  AND NOT EXISTS (SELECT 1 FROM account_move_line l
                  WHERE l.move_id=m.id AND l.display_type='payment_term');
```
- **The chatter tells the story:** the order carries "Automatic invoicing failed: ..." at the exact minute the zombie was born — correlate before blaming the accountant.
- **`message_post` after the rollback is safe** (note subtype, no external notify), so the failure stays visible.
- **Any `except Exception` around a multi-record `create()`/`write()` needs `cr.savepoint()`** — same family as [controller-catching-create-error-without-savepoint-commits-partial-record](../security/controller-catching-create-error-without-savepoint-commits-partial-record.md).

## Verification

- Reproduced in `odoo shell`: copy SO → confirm → swallowed crash → zombie draft (10 zero-amount product lines, no payment_term line) → `action_post()` → `payment_state='paid'`, residual 0.
- With the savepoint fix, same scenario: order confirmed, `invoice_ids` empty, failure message posted.
- Regression tests added: `sale_visit/tests/test_auto_invoice_atomicity.py`.

## References

- Fixed file: [sale_visit/models/sale_order.py](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/models/sale_order.py)
- Trigger: [customer_level_chart/models/res_partner.py](file:///Users/gamal/odoo/odoo19.0/custom/customer_level_chart/models/res_partner.py) (`name = fields.Char(translate=True)`)
- Related KB: [translated_many2one_search](translated_many2one_search.md), [controller-catching-create-error-without-savepoint-commits-partial-record](../security/controller-catching-create-error-without-savepoint-commits-partial-record.md), [receivable-payable-account-move-line-due-date-constraint](receivable-payable-account-move-line-due-date-constraint.md)
