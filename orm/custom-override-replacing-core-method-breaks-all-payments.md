# A custom override that REPLACES a core money method breaks everything the method serves

**Category:** ORM / Accounting / Third-party customs
**Date:** 2026-08-10
**Project:** activity (client's `vz_bankcharges` on the restored production-shaped DB)

## Symptom
Every inbound payment registration fails with `account_move_line_check_accountable_required_fields` — an extra zero-amount move line with `account_id = NULL` appears in every payment move. App webhooks can never mark invoices paid; refund flows (which require a paid invoice) are unreachable.

## Root cause
A client custom module overrode `account.payment._prepare_move_line_default_vals` by REPLACING the whole body (copy-pasted core + edits) instead of extending it. It unconditionally injected a "bank charge" line — even with charge = 0 and the feature toggle off — with `account_id = payment_method_line_id.bank_charge_account_2.id`, which is `False` when unconfigured → NULL-account line → constraint violation on EVERY payment.

## Fix pattern (surgical, preserves the feature)
Early-return to core when the customization isn't actually in play:
```python
def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=False):
    self.ensure_one()
    if not self.vz_bank_charge or not self.payment_method_line_id.bank_charge_account_2:
        return super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance)
    ...  # custom split only when a real charge + configured account exist
```

## Related hardening (same session)
- Never swallow a payment-registration failure as "a race": re-check `invoice.payment_state`; if still unpaid → re-raise (a silent done-txn with an unpaid invoice blocks every downstream money flow).
- Production HTTP code paths run as the PUBLIC user: company-scope accounting operations (`with_company(invoice.company_id)`) on payment registration AND invoice reversal, or hit NULL accounts / "Expected singleton: res.company()".

## Rule of thumb
When a third-party module copy-pastes a core method body, treat every core upgrade and every "impossible" accounting error as its suspect. Diff the override against core FIRST. And restoring the client's real backup locally is the only test bed that catches this class — clean test DBs never load their customs.
