# Money Flows (Commission/Settlement) Must Reverse on Refund, Cancel, and Reset-to-Draft

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `account`, `commission`, `refund`, `out_refund`, `reversal`, `idempotency`, `data-integrity`

---

## Problem

> A derived money record (sales commission, marketing settlement, accrual) is created when an invoice posts, but nothing **removes or reduces** it when the source is later refunded, cancelled, or reset to draft. Because the create side is (correctly) idempotent — "don't create twice" — the same guard also prevents correction. Errors are **directional**: they only ever push the total upward, never wash out. Over a year this is systematic over-payment that surfaces only at reconciliation.

```python
# salesperson_commission — only out_invoice is ever considered; out_refund is ignored everywhere:
moves = env['account.move'].search([
    ('move_type', '=', 'out_invoice'),    # credit notes (out_refund) never reduce commission
    ('state', '=', 'posted'),
])
moves._create_or_update_commission()
# account_move.py has NO override of button_draft / button_cancel / _post,
# so an invoice that is commissioned → reset to draft → edited → re-posted keeps the OLD commission forever.
```

## Root Cause

Two missing reversals: (1) **refunds** — a credit note (`out_refund`) is a separate posted move that should reduce the commission of the invoice it reverses, but the logic filters to `out_invoice` only; (2) **state changes** — `button_draft`/`button_cancel` on `account.move` are not overridden, so the linked money record is never deleted/regenerated. The idempotency guard (`if commission already exists: skip`) then locks in the stale value.

## Solution ✅

```python
class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        # handle refunds: reduce/clawback the commission of the reversed invoice
        for move in posted.filtered(lambda m: m.move_type == 'out_refund' and m.reversed_entry_id):
            move.reversed_entry_id._create_or_update_commission()  # recompute net of this refund
        posted.filtered(lambda m: m.move_type == 'out_invoice')._create_or_update_commission()
        return posted

    def button_draft(self):
        res = super().button_draft()
        self._reverse_linked_commission()   # delete/zero + unlink from any draft settlement
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self._reverse_linked_commission()
        return res
```

For settlement-style records that **post a journal entry**, cancel must call `account_move_id._reverse_moves(...)` (or block cancel with a `UserError` until reversed) — flipping `state='cancelled'` and freeing the lines double-books the money. Also guard `action_confirm` against re-posting when `account_move_id` is already set, and add a `state != 'draft'` guard so re-confirm can't create a second entry.

## ⚠️ Pitfalls

- Round every money figure through `currency.round()` / `float_round(precision_rounding=...)`. Raw float multiplication drifts, and a sub-cent drift against a `== 100` / `< threshold` bonus gate flips a real payout.
- Idempotency keyed on mere *existence* blocks correction. Key it on a hash of `(amount, salesperson, lines)` so a genuine change regenerates.
- Re-posting after edit must regenerate, not keep the original — test the post → draft → edit → re-post cycle explicitly.
- All these directional errors (refund ignored, no reversal, lifetime double-count) push the **same way**, so they *sum* — they don't cancel out.

## Verification

```bash
# Does the money module even know refunds/cancels exist?
grep -rn "out_refund\|reversed_entry\|button_draft\|button_cancel\|_reverse_moves" custom/<module>/
# Manual: post invoice → confirm commission → create credit note → confirm commission shrank.
#         post invoice → reset to draft → confirm commission gone/regenerated.
```

## References

- Related file: `orm/write-override-atomicity-pattern.md`
- Related file: `orm/automatic-invoice-reconciliation-customer-advances.md`
