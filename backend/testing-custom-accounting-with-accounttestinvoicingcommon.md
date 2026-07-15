# Testing custom accounting code: `AccountTestInvoicingCommon` gotchas (groups, author email, payment_state)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend (testing)                          |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `account`, `AccountTestInvoicingCommon`, `payment_state`, `message_post`, `groups`, `deferred`

---

## Problem

A custom module that creates invoices/payments must be tested against a real
chart of accounts. The right base class is
`odoo.addons.account.tests.common.AccountTestInvoicingCommon` (it builds a test
company with a CoA + taxes). Three things then bite in a row:

```
# 1) Your own model's ACL rejects the test user
AccessError: You are not allowed to create 'Activity' (activity.activity) records.
    - Activity Platform/Activity Admin

# 2) Posting a move as a freshly-created user with no email
UserError: Unable to send message, please configure the sender's email address.
  ...account_move.py _post → move.message_post(body=msg) → _message_compute_author(raise_on_email=True)

# 3) Asserting the invoice is 'paid' after registering a payment
AssertionError: 'in_payment' != 'paid'
```

## Root Cause

1. `AccountTestInvoicingCommon`'s `cls.env.user` is an **accounting** test user
   with account groups only — it has none of your module's security groups, so
   `create()` on your models fails the model-level ACL.
2. `account.move._post()` calls `move.message_post(...)`. `_message_compute_author`
   runs with `raise_on_email=True`, so the **acting user must have an email**.
   The default test admin has one; any `res.users` you create in the test does
   **not** unless you set it. (A deferred-revenue line makes `_post` generate and
   post *extra* moves, widening the window for this.)
3. Registering a payment via `account.payment.register` moves the invoice to
   **`in_payment`**, not `paid`. It only becomes `paid` after the payment is
   reconciled with a bank statement — or immediately if the payment journal has
   no outstanding account. `in_payment` is the correct post-registration state.

## Solution ✅

```python
class TestPayment(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        # (1) grant your module's top group to the acting user
        cls.env.user.groups_id |= cls.env.ref('your_module.group_admin')

    def test_x(self):
        # (2) any user that will POST a move needs an email
        approver = self.env['res.users'].create({
            'name': 'Approver', 'login': 'approver',
            'email': 'approver@example.com',
            'groups_id': [(6, 0, [ ... , self.env.ref('account.group_account_manager').id])],
        })
        ...
        # (3) accept either settled state
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
```

Pin lookups so they don't depend on the generic test chart: set config params to
a tax/account you create (e.g. a 15% sale tax + `company_data['default_account_revenue']`).

## ⚠️ Pitfalls

- Don't "fix" (2) by switching the model's own note to `_message_log` — the
  offending `message_post` is inside **core** `account.move._post`, not your code.
  Give the user an email (which every real user has anyway).
- Granting the top group works because of `implied_ids` chaining (super admin →
  admin → coach). Grant the highest so create/write/unlink all pass.
- A credit note created by `_reverse_moves` **inherits `deferred_start/end`** from
  the source line, so posting it re-runs deferred generation — expected, but it's
  why the author-email error surfaced on refund approval, not on first invoicing.

## Verification

```bash
odoo-bin -c conf -d db -u <module> --test-enable --test-tags /<module> \
  --stop-after-init --http-port 8911 --gevent-port 8912 --max-cron-threads=0
# => 0 failed, 0 error(s)
```

## References

- Code: `activity/activity_payment/tests/test_payment.py`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- Related file: `security/sod-approval-checks.md`
