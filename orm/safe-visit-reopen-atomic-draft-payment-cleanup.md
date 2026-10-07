# Safe Visit Reopen: Atomic Deletion of Draft Payments and Credit Notes with Strict Posted Lock

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / models                               |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `sale.visit`, `account.payment`, `account.move`, `reopen`, `idempotency`, `field-sales`, `atomic`

---

## Problem

In field mobility and van sales architectures (e.g. `sale_visit`), closing a representative's field visit automatically triggers downstream financial artifacts:
1. Draft inbound customer payments (`account.payment` linked to collection lines).
2. Draft customer credit notes (`account.move` for delivery shortfalls and returns).

If a representative or supervisor needs to **reopen** a completed visit (to fix a typo, add an omitted survey photo, or correct an order line), a naive `action_reopen()` that merely sets `state = 'in_progress'` causes severe financial corruption:
- Re-ending the visit spawns **duplicate** draft payments and duplicate credit notes.
- Worse, if an accountant or cashier already validated and posted (`state == 'posted'`) the customer payment, a blanket delete crashes with a `UserError` ("You cannot delete a posted payment"), or if forced via SQL/sudo, breaks bank reconciliation and general ledger balance.

## Root Cause

Field operations must distinguish between **unposted staging artifacts** (which belong to the field session lifecycle) and **posted accounting entries** (which belong to the statutory financial ledger). Once a payment is posted, it has legal and tax reality and must never be silently removed by a field user reopening a route visit.

## Solution ✅

Implement a two-tier atomic reopening lifecycle:
1. Search and unlink/delete *only* linked `account.payment` and `account.move` records that are strictly in `draft` state.
2. If any linked payment or credit note is already in `posted` state, **strictly protect it**: keep it linked, lock destructive deletion, and log a clear audit note in the chatter informing the cashier.

```python
def action_reopen_visit(self):
    self.ensure_one()
    if self.state != 'done':
        raise UserError(_("Only completed visits can be reopened."))

    # 1. Atomic cleanup of unposted draft payments
    draft_payments = self.env['account.payment'].search([
        ('visit_id', '=', self.id),
        ('state', '=', 'draft')
    ])
    if draft_payments:
        draft_payments.unlink()

    # 2. Check if any payments are already posted by cashier
    posted_payments = self.env['account.payment'].search([
        ('visit_id', '=', self.id),
        ('state', '=', 'posted')
    ])
    if posted_payments:
        self.message_post(body=_(
            "⚠️ Notice: Visit was reopened, but %d posted payment(s) were preserved in accounting."
        ) % len(posted_payments))

    # 3. Clean up unposted draft shortfall/return credit notes
    draft_credit_notes = self.env['account.move'].search([
        ('visit_id', '=', self.id),
        ('state', '=', 'draft'),
        ('move_type', '=', 'out_refund')
    ])
    if draft_credit_notes:
        draft_credit_notes.unlink()

    # 4. Safely revert visit status
    self.write({
        'state': 'in_progress',
        'check_out_datetime': False,
    })
    return True
```

## ⚠️ Pitfalls

- **Do NOT use raw SQL deletion:** Calling `self.env.cr.execute("DELETE FROM account_payment WHERE ...")` bypasses ORM constraints, leaving orphaned relational records and invalid payment state caches.
- **Relational Field Reset:** Ensure that when unlinking draft credit notes, any One2many / Many2one pointer on the visit (e.g. `shortfall_credit_note_id`, `return_invoice_id`) is properly cleared to avoid `MissingError`.
- **Permission Boundaries:** Reopening should only be granted to authorized supervisors (`supervisor` or `sales_manager`), never to general van drivers without supervisor approval.

## Verification

1. Create and complete a field visit with a 500 EGP cash collection line -> System generates draft `account.payment` ID X.
2. Reopen the visit prior to cashier posting -> Payment ID X is cleanly unlinked; no duplicate exists upon re-closing.
3. Complete visit and have cashier post payment ID Y -> Reopen visit -> Payment ID Y remains posted and untouched in accounting; visit state reverts cleanly to `in_progress`.
