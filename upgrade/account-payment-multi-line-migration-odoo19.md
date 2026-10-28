# Upgrading Custom Multi-Invoice `account.payment` Modules from Odoo 15/16 to Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `account.payment`, `account.move.line`, `multi_payment`, `reconciliation`, `_synchronize_to_moves`, `outstanding_account_id`, `odoo19`, `upgrade`

---

## Problem

When porting legacy (Odoo 14/15/16) custom payment modules (such as `dev_invoice_multi_payment` / Multiple Invoice Payment) to **Odoo 19.0**, the module fails at both installation and runtime with multiple errors:

```text
1. ParseError: Invalid view architecture: <tree>, <seperator>, attrs="{...}", <act_window>
2. AttributeError: 'account.payment' object has no attribute 'is_internal_transfer'
3. AttributeError: 'account.move.line' object has no attribute '_get_default_line_name'
4. AttributeError: 'res.currency' object has no attribute '_compute'
5. ValueError: Invalid field 'ref' on model 'account.payment'
6. UserError: You cannot change the amount of a payment with multiple liquidity lines.
7. ValidationError / Null value in column "account_id" of relation "account_move_line" when outstanding_account_id is empty
```

## Root Cause

Between Odoo 15 and Odoo 19, `account.payment` underwent a major architectural redesign:
1. **Deferred Journal Entry Creation:** In Odoo 18/19, `account.payment` in `draft` state no longer creates a draft `account.move` (`move_id` is `False` until confirmation/posting). Assuming `self.move_id` exists on a draft payment silently skips move line generation or crashes.
2. **Removed & Renamed Fields/Helpers:**
   - `account.payment.ref` was replaced by `account.payment.memo`.
   - `account.payment.is_internal_transfer` was removed.
   - `account.move.line._get_default_line_name()` was removed and replaced by `account.payment._get_aml_default_display_name_list()`.
   - `account.payment.payment_method_id` is now a related field on `payment_method_line_id.payment_method_id`; wizards must resolve and pass `payment_method_line_id`.
   - `res.currency._compute()` was removed in favor of `currency._convert(amount, to_currency, company, date)`.
3. **Move Synchronization Guard (`_synchronize_to_moves`):** `_synchronize_from_moves` was removed, and `_synchronize_to_moves` raises a `UserError` if a draft payment move has more than one liquidity line (`len(liquidity_lines) > 1`).
4. **Optional `outstanding_account_id`:** In Odoo 18/19, `payment_method_line_id.payment_account_id` (`outstanding_account_id`) is not set by default on standard journals unless explicitly configured or resolved via `journal_id.default_account_id` / `_get_outstanding_account()`.

## Solution ✅

1. **Bypass `_synchronize_to_moves` for Multi-Line Payments:**
   ```python
   def _synchronize_to_moves(self, changed_fields: set) -> None:
       standard_payments = self.filtered(lambda p: p.payment_for != 'multi_payment')
       if not standard_payments:
           return
       return super(AccountPayment, standard_payments)._synchronize_to_moves(changed_fields)
   ```

2. **Resolve Liquidity Account Safely & Build Default Line Label via Odoo 19 API:**
   ```python
   def _get_multi_payment_line_label(self) -> str:
       self.ensure_one()
       default_line_name = ''.join(x[1] for x in self._get_aml_default_display_name_list() if x[1])
       return self.payment_reference or self.memo or default_line_name

   def _get_multi_payment_liquidity_account(self):
       self.ensure_one()
       return (
           self.outstanding_account_id
           or self.journal_id.default_account_id
           or self._get_outstanding_account(self.payment_type)
       )
   ```

3. **Create or Update `move_id` Using `_generate_move_vals(line_ids=...)` and Link `matched_payment_ids`:**
   ```python
   move_commands = [Command.create(vals) for vals in line_vals_list]
   if payment.move_id:
       if payment.move_id.state != 'draft':
           payment.move_id.button_draft()
       payment.move_id.with_context(skip_invoice_sync=True).write({
           'date': payment.date,
           'ref': payment.memo,
           'journal_id': payment.journal_id.id,
           'currency_id': payment.currency_id.id,
           'partner_id': payment.partner_id.id,
           'line_ids': [Command.clear()] + move_commands,
       })
   else:
       move_vals = payment._generate_move_vals(line_ids=move_commands)
       payment.move_id = self.env['account.move'].create(move_vals).id

   payment.move_id.action_post()
   target_state = 'paid' if liquidity_account.account_type == 'asset_cash' else 'in_process'
   payment.write({
       'state': target_state,
       'invoice_ids': [Command.set(payment.dev_invoice_line_ids.mapped('invoice_id').ids)],
   })
   ```

4. **Resolve `payment_method_line_id` in Payment Wizards:**
   ```python
   available_lines = self.journal_id._get_available_payment_method_lines(self.payment_type)
   payment_method_line = available_lines.filtered(lambda l: l.code == 'manual')[:1] or available_lines[:1]
   ```

## ⚠️ Pitfalls

- **Never assume `payment.move_id` exists in `draft` state in Odoo 19:** Always branch on `if payment.move_id:` vs `payment._generate_move_vals(line_ids=...)`.
- **Match Invoice Receivable/Payable Account:** When generating counterpart lines per invoice for `js_assign_outstanding_line()`, always read the specific invoice's `asset_receivable` / `liability_payable` line account rather than assuming all invoices of a partner share `payment.destination_account_id`.
- **Link `invoice_id.matched_payment_ids` and `payment.invoice_ids`:** Without linking these Many2many fields in Odoo 19, payment smart buttons and invoice payment state badges may not reflect the payment prior to full bank reconciliation.

## Verification

```bash
./odoo-bin -c custom.conf -d <db> -u dev_invoice_multi_payment --stop-after-init
```

## References

- `addons/account/models/account_payment.py` (`_generate_move_vals`, `_synchronize_to_moves`, `action_post`)
- `addons/account/wizard/account_payment_register.py` (`_reconcile_payments`)
