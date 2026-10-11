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

- **Configuration Root Cause:** If this happens natively in POS without any custom code changes, it is almost certainly a configuration issue. An accountant may have accidentally changed the "Account Type" of the POS Receivable Account or a Payment Method's outstanding account from `Current Assets` (أصول متداولة) or `Bank and Cash` to `Receivable` (حسابات عملاء).
- **Frontend Masking Error:** In Odoo 18.0 POS, this backend `UserError` might be masked on the frontend by a JavaScript `ReferenceError: RPCError is not defined` during `_finalizeValidation`. This happens because the frontend tries to catch the backend error but fails if `RPCError` isn't resolved properly in the minified bundle. Always check the server logs for the real `UserError`.
- Forgetting to apply `display_type` when creating custom intermediate POS accounts in code.
- Trying to add `date_maturity` field manually without adding `display_type`. The constraint strictly checks `display_type == 'payment_term'`, not just the presence of a date.

## Verification

> Trigger the action that manually creates the accounting entry (e.g. paying an invoice from point of sale). The `account.move` and `account.move.line` should be created and posted without throwing the validation error.
