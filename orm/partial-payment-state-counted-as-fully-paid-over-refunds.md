# `payment_state == 'partial'` Counted as Fully Paid Over-Refunds the Customer

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                         |
| Odoo Versions | 16, 17, 18, 19                              |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-08-19                                  |
| Author        | ENG/Gamal Mansour                           |

**Tags:** `orm`, `account`, `refund`, `payment_state`, `partial`, `amount_residual`, `credit-note`, `money-integrity`

---

## Problem

A "how much did this customer actually pay?" helper gates on `payment_state`
and then returns the **invoiced** amount:

```python
def _activity_own_paid_amount(self):
    invoice = self.invoice_id
    if not (invoice and invoice.state == 'posted'
            and invoice.payment_state in ('paid', 'in_payment', 'partial')):
        return 0.0
    return self._activity_own_invoice_amount()      # <-- INVOICED, not PAID
```

`'paid'` and `'in_payment'` are fine — the full amount really was registered.
`'partial'` is not: the customer paid **less** than the invoice, but the helper
reports the full line total as received.

Every downstream refund calculation then over-pays:

```
Invoice           1000.00
Actually paid      300.00   (payment_state = 'partial')
Cancel before any session  ->  factor = 1.0
Refund computed  = 1000.00 * 1.0 = 1000.00
Net loss           700.00 per occurrence
```

Worse, the usual safety net does not fire. A guard like

```python
if abs(credit_note.amount_total - expected_amount) > tolerance:
    raise UserError(...)
```

compares the credit note against **the same wrong number**, so it passes and the
inflated note is posted and paid out.

## Root Cause

`payment_state` is a **status**, not an amount. Odoo sets `'partial'` as soon as
*any* payment is reconciled against the move, with the outstanding balance
sitting in `amount_residual`. Treating the state as a boolean ("settled enough,
so take the invoiced figure") throws away the only field that carries the
difference.

Partial states arrive from ordinary back-office activity even when the API flow
always registers the full amount:

- an accountant registering a down payment or an instalment,
- a bank-statement line reconciled for less than the invoice,
- a credit note partially applied,
- a rounding/write-off left open.

So "our controller always pays in full" is not a defence — the ERP has other doors.

## Solution ✅

Derive the paid share from `amount_residual`, and scale the per-line share by the
real ratio:

```python
def _activity_own_paid_amount(self):
    """This record's own share of what was ACTUALLY received."""
    self.ensure_one()
    invoice = self.invoice_id
    if not (invoice and invoice.state == 'posted'
            and invoice.payment_state in ('paid', 'in_payment', 'partial')):
        return 0.0
    own = self._activity_own_invoice_amount()
    total = invoice.amount_total
    if not total:
        return 0.0
    # 'paid'/'in_payment' -> residual 0 -> ratio 1.0 -> byte-identical to before.
    paid_ratio = max(0.0, min(1.0, (total - invoice.amount_residual) / total))
    return invoice.currency_id.round(own * paid_ratio)
```

If the business cannot accept a pro-rata refund on a partially-paid invoice, the
alternative is to **block** it and route to a human:

```python
if invoice.payment_state == 'partial':
    raise UserError(_(
        'Invoice %s is only partially paid — a refund must be reviewed '
        'manually.', invoice.name))
```

Either is defensible. Silently treating partial as full is not.

## ⚠️ Pitfalls

- `amount_residual` is in the **invoice currency**; `amount_residual_signed` is in
  company currency. Mixing them on a foreign-currency invoice reintroduces the
  same class of error in a subtler form.
- A **credit note already applied** to the invoice also reduces `amount_residual`.
  It looks like "paid" to the ratio above, so refunding again double-refunds.
  Exclude already-reversed amounts, or check `invoice.reversal_move_id` first.
- Do not compute the ratio from `payment_state` alone by mapping
  `{'paid': 1.0, 'partial': 0.5}` — the real fraction is arbitrary.
- The self-check `abs(note.amount_total - expected) > tolerance` is only as good
  as `expected`. A money guard that compares a number to *itself derived the same
  way* verifies nothing. Anchor at least one side on the ledger
  (`amount_residual`, reconciled `account.payment` lines).
- `payment_state` is also `'reversed'` and `'blocked'` in v16+. An `in (...)`
  allow-list silently misclassifies those as "nothing paid" — usually the safe
  direction, but state it deliberately.

## Verification

```python
# In a TransactionCase: partial payment must yield a partial refund.
invoice = sub._create_invoice()                 # total 1000
self.env['account.payment.register'].with_context(
    active_model='account.move', active_ids=invoice.ids
).create({'amount': 300.0})._create_payments()

self.assertEqual(invoice.payment_state, 'partial')
self.assertEqual(invoice.amount_residual, 700.0)
self.assertEqual(sub._activity_own_paid_amount(), 300.0)   # NOT 1000.0

amount, factor = sub._activity_refund_amount_and_factor()
self.assertEqual(amount, 300.0)                            # NOT 1000.0
```

```sql
-- Production sanity sweep: any refund larger than what came in?
SELECT r.id, r.amount, m.amount_total, m.amount_residual
FROM   activity_refund_request r
JOIN   activity_subscription s ON s.id = r.subscription_id
JOIN   account_move m          ON m.id = s.invoice_id
WHERE  r.amount > (m.amount_total - m.amount_residual);
```

## References

- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- Related file: `orm/automatic-invoice-reconciliation-customer-advances.md`
- Related file: `orm/invoice-paid-on-post-zombie-from-swallowed-create-error.md`
