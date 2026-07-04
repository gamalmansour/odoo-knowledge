# Receivable/Payable Account Journal Item Due Date Constraint

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `account`, `journal-item`, `receivable`, `payable`, `due-date`, `constraint`, `display_type`

---

## Problem

> When creating custom `account.move.line` (journal items) for payment or invoice reconciliation in Odoo (especially in POS or custom accounting modules), the system throws a `UserError` blocking the creation of the move lines if the account used is of type `asset_receivable` or `liability_payable`.

```
UserError: Any journal item on a receivable account must have a due date and vice versa.
```

## Root Cause

> The `_check_payable_receivable` constraint in `account.move.line` strictly requires that any journal item linked to an account of type `asset_receivable` or `liability_payable` MUST have its `display_type` set to `'payment_term'`. Odoo implicitly relies on `display_type == 'payment_term'` to manage due dates and reconciliation for these types of accounts. When manually constructing dictionary values for move lines in code (e.g., using `_credit_amounts` or `_debit_amounts` manually), omitting `display_type` triggers this constraint.

## Solution ✅

> Ensure that any dictionary passed for creating `account.move.line` includes `'display_type': 'payment_term'` whenever the target `account_id` is a receivable or payable account. 

```python
# Before
credit_line_vals = pos_session._credit_amounts({
    'account_id': accounting_partner.property_account_receivable_id.id,
    'partner_id': accounting_partner.id,
    'move_id': payment_move.id,
}, amounts['amount'], amounts['amount_converted'])

# After - Add 'display_type': 'payment_term'
credit_line_vals = pos_session._credit_amounts({
    'account_id': accounting_partner.property_account_receivable_id.id,
    'partner_id': accounting_partner.id,
    'move_id': payment_move.id,
    'display_type': 'payment_term', # MUST be added for receivable/payable accounts
}, amounts['amount'], amounts['amount_converted'])
```

## ⚠️ Pitfalls

- Forgetting to apply this when creating intermediate POS accounts like `account_default_pos_receivable_account_id` which might be configured as a receivable account.
- Trying to add `date_maturity` field manually without adding `display_type`. The constraint strictly checks `display_type == 'payment_term'`, not just the presence of a date.

## Verification

> Trigger the action that manually creates the accounting entry (e.g. paying an invoice from point of sale). The `account.move` and `account.move.line` should be created and posted without throwing the validation error.
