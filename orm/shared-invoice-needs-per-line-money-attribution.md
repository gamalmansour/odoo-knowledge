# Combining several billable records onto ONE shared invoice breaks every refund/reversal formula that reads `invoice.amount_total` as "this record's money"

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `account.move`, `account.move.line`, `shared-invoice`, `refund`, `credit-note`, `reversal`, `idempotency`, `context-flag`, `money-integrity`

---

## Problem

A platform bills one order-like record (subscription, membership period, rental
month, …) per invoice, and refund/cancel math reads `invoice.amount_total` as a
shorthand for "what this record's money is". That shorthand is correct only
because, today, the invoice never has any other record's money on it.

The moment a feature combines SEVERAL of those records onto ONE invoice (e.g.
"pay for 3 months together, one invoice, one payment" — a completely ordinary,
client-requested billing improvement), every formula still reading
`invoice.amount_total` silently becomes wrong: refunding/cancelling ONE of the
combined records refunds or reverses the WHOLE invoice — every sibling
record's money too. Nothing crashes; the numbers are just quietly 2-3x too
large. The same blind spot usually hides in more than one place at once:
the refund-amount formula, the credit-note LINE builder (`invoice_line_ids`
with no per-record filter — a full `_reverse_moves()` mirror has no
"reverse X% of it" argument at all), any admin-side "refund amount" cap
constraint, and any manual-amount → fraction/factor derivation.

## Root Cause

`account.move` (and Odoo's own `_reverse_moves()`) has no first-class concept
of "which of several unrelated business records this invoice's TOTAL belongs
to" — that association only exists at the LINE level, if you put it there
yourself. A single-record-per-invoice history means every "money for this
record" read was actually a "money for this invoice" read that happened to be
correct by construction; the bug isn't in the math, it's in the implicit
assumption that got baked into the formula's INPUT.

## Solution ✅

1. **Tag every invoice LINE with the business record it bills**, not just
   the move (a move-level singular `Many2one` back-link is fine for a
   single-record invoice and for the credit note the record's refund
   eventually produces — a credit note is still 1:1 per record even once
   invoices aren't — but it cannot express "3 lines, 3 different records, 1
   invoice"):
```python
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    my_record_id = fields.Many2one('my.billable.record', index=True,
                                    copy=False, ondelete='set null')
```
   Stamp it in the ONE shared line-builder every invoicing path already goes
   through (single-record invoice AND the new shared invoice) — one
   universal tag, never a per-caller special case.

2. **Replace every "money for this record" read with a line-scoped one,
   never the move total**:
```python
def _own_invoice_lines(self):
    self.ensure_one()
    lines = self.invoice_id.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
    if not lines.mapped('my_record_id'):
        return lines  # legacy/hand-built invoice predating the tag -> one record per invoice was the only shape possible then
    return lines.filtered(lambda l: l.my_record_id.id == self.id)

def _own_invoice_amount(self):
    return sum(self._own_invoice_lines().mapped('price_total'))  # tax-inclusive, per line
```
   Audit for EVERY call site sharing the old assumption — it is rarely just
   one: the refund-amount formula, the credit-note line builder (`filtered
   lambda l: l.display_type == 'product'`, no per-record filter — see
   `partial-credit-note-scaled-lines-and-display-type-default.md`), any
   admin-facing "refund cannot exceed X" cap constraint, and any
   manual-amount → factor/fraction derivation. All four should call through
   the SAME `_own_invoice_amount()` helper — one formula, not four to keep in
   sync.

3. **A full-mirror reversal (`_reverse_moves()`) has no partial mode and no
   per-record scope — branch on "is this invoice shared" before using it**:
```python
def _reverse_invoice(self, reason=None):
    if self._invoice_is_shared():           # >1 distinct my_record_id on its product lines
        return self._scoped_credit_note(1.0, self._own_invoice_amount(), reason=reason)
    return invoice.with_company(invoice.company_id)._reverse_moves([...])  # unchanged, single-record path
```
   Reuse the SAME scoped-credit-note builder a genuinely PARTIAL refund uses,
   just at factor `1.0` — one scoped-reversal mechanism, not two that can
   drift apart. A single-record invoice keeps the original full-mirror path
   untouched (byte-identical to before this feature existed).

4. **Confirming/activating several records into ONE shared invoice needs a
   way to suppress each record's OWN "auto-invoice on confirm" side effect**,
   if one exists, without skipping its validation. A context flag is the
   right tool — it is the one thing a batch-confirm-then-shared-invoice flow
   needs to differ on, and it defaults to off so every existing single-record
   caller is untouched:
```python
def action_confirm(self):
    res = super().action_confirm()        # validation always runs
    if self.env.context.get('skip_auto_invoice'):
        return res
    for rec in self.filtered(lambda r: r.state == 'confirmed' and not r.invoice_id):
        rec._create_invoice()
    return res
```
   Without this, batch-confirming N records before building the shared
   invoice creates N individual orphaned invoices first (each one's own
   `action_confirm` override fires normally), and the shared invoice then
   overwrites their `invoice_id` — leaving N posted, unreferenced, unpaid
   invoices in the books forever. This is the single most dangerous failure
   mode in this whole pattern; closing it is structural (the flag), not a
   cleanup step.

5. **Webhook/payment-registration idempotency needs NO changes.**
   `account.payment.register` and a `(gateway, provider_reference)`-unique
   transaction record are already invoice-total-based and record-count
   agnostic — a shared invoice's ONE payment settles the WHOLE invoice in one
   shot exactly like a single-record invoice's payment does. Don't touch
   that layer; the bug and the fix are entirely in the refund/reversal
   direction, not the payment direction.

## ⚠️ Pitfalls

- The move-level singular back-link field is still correct to KEEP (for
  credit notes, and as a fallback when nothing on the invoice is tagged) —
  don't delete it thinking the new line-level field replaces it.
- Ownership/access checks that read the move-level singular field (e.g. "can
  this caller download this invoice's PDF") need the SAME line-level
  widening — a shared invoice can legitimately belong to several distinct
  owners (e.g. two siblings' subscriptions on one guardian's invoice), and a
  singular field can only ever point at one of them.
- The "fall back to every product line when NONE carry the tag" rule must be
  exactly that — NONE, not "this record's own tag is empty". Falling back
  per-record instead of per-invoice would silently widen a genuinely shared,
  partially-tagged invoice to include a sibling's line.
- Test the SHARED case explicitly for "does refunding record A leave record
  B's `invoice_id`, state, and own line amounts untouched" — a green
  single-record regression suite proves nothing about the new shared shape;
  the old bug's own test fixtures never had more than one record per invoice
  to expose it.

## Verification

```python
# 3 records combined on one invoice, 100 (+15% VAT = 115) each -> 345 total.
# Refund/cancel ONE of them:
self.assertEqual(refund.amount, 115.0)          # its own share
self.assertNotEqual(refund.amount, invoice.amount_total)  # never the 3x total
sibling.invalidate_recordset()
self.assertEqual(sibling.state, 'confirmed')     # untouched
self.assertEqual(sibling.invoice_id, invoice)    # still on the shared invoice
self.assertFalse(sibling.credit_note_ids)        # no leaked reversal
```

## References

- Related file: `orm/partial-credit-note-scaled-lines-and-display-type-default.md`
  (the credit-note LINE-filter pitfall this pattern's step 2/3 builds on)
- Related file: `misc/httpcase-public-user-company-mismatch-credit-note-singleton.md`
  (company-scope every accounting call under `auth='public'` — applies
  identically to the new shared-invoice create/post path)
- Related file: `security/controller-catching-create-error-without-savepoint-commits-partial-record.md`
  (the confirm+invoice+transaction batch belongs in one savepoint)
- Code: `activity/activity_payment/models/activity_subscription.py`
  (`_activity_checkout`, `_activity_own_invoice_lines`,
  `_activity_own_paid_amount`, `_activity_invoice_is_shared`,
  `action_confirm`'s `activity_skip_auto_invoice` context flag)
