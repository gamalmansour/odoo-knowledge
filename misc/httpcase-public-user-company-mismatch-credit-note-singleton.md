# HttpCase money test with a non-default test company crashes deep in credit-note reversal: "Expected singleton: res.company()"

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | 17 (mechanism is general to `auth='public'`) |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `httpcase`, `auth-public`, `multi-company`, `account.move`, `credit-note`, `exchange-difference`, `public-user`

---

## Problem

An `AccountTestInvoicingHttpCommon` test creates its own test company
(`cls.company_data['company']`, the standard `AccountTestInvoicingCommon`
pattern), posts a real invoice against it, then hits an endpoint via
`self.url_open(...)` that reverses the invoice with a credit note
(`account.move._reverse_moves()` + `action_post()`). The SAME code path
called directly (no HTTP) in a plain `TransactionCase`/`AccountTestInvoicingCommon`
test works fine — but via HTTP it 500s deep inside account's reconciliation
code:

```
File ".../account_move_line.py", line 2801, in _prepare_exchange_difference_move_vals
    accounting_exchange_date = journal.with_context(...).accounting_date if journal else date.min
File ".../account_journal.py", line 432, in _compute_accounting_date
    journal.accounting_date = temp_move._get_accounting_date(move_date, has_tax)
File ".../account_move.py", line 4618, in _get_violated_lock_dates
    return self.company_id._get_violated_lock_dates(invoice_date, has_tax)
File ".../company.py", line 384, in _get_violated_lock_dates
    self.ensure_one()
ValueError: Expected singleton: res.company()
```

## Root Cause

Odoo dispatches every `auth='public'` route as `base.public_user` (see
`ir_http.py::_auth_method_public`), NOT as the test suite's own admin user
(`cls.env.user`, the one `AccountTestInvoicingCommon.setUpClass()` actually
scopes to the fresh test company). `request.env.company` for the HTTP
request is therefore `public_user`'s own default company — normally
`base.main_company` — which has nothing to do with the invoice's real
company. Reconciliation code that computes a lock-date via a fresh/virtual
move (`temp_move`) resolves its company implicitly through `self.env.company`
in places, and when that env-default company doesn't line up with the
recordset actually being processed, a downstream `ensure_one()` on an
empty/ambiguous `company_id` blows up. Simple `action_post()` on a freshly
created invoice doesn't hit this (no reconciliation/exchange-difference
branch), which is why routes like `confirm` (invoice creation) work fine via
HTTP while a REVERSAL (credit note + `_reconcile_reversed_moves`) doesn't.

## Solution ✅

Give `base.public_user` the SAME company as the test's own company for the
duration of the test class, in `setUpClass`:

```python
public_user = cls.env.ref('base.public_user').sudo()
public_user.write({'company_id': cls.company.id, 'company_ids': [(4, cls.company.id)]})
```

This is a test-only, class-scoped write — `TransactionCase`'s per-class
savepoint rolls it back after the class finishes, so it never leaks into
other test classes or a real database.

## ⚠️ Pitfalls

- A plain (non-HTTP) `AccountTestInvoicingCommon` test of the SAME model
  method will never expose this — it runs under `cls.env.user`, which the
  base class already scopes to the test company. Only surfaces when a route
  is exercised via `url_open`/`HttpCase`.
- Simple invoice creation/posting via HTTP does NOT hit this — only paths
  that reconcile/reverse (credit notes, exchange-difference computation) do.
  Don't assume "HTTP + custom company" is broken in general.
- Don't "fix" this by switching the test to use `base.main_company` instead
  of a fresh test company — that just relocates the assumption and can
  collide with other tests' chart-of-accounts setup on the same company.

## Verification

```bash
# Re-run the HTTP-level money test suite; the credit-note-reversal route
# (a paid/unpaid cancel that reverses a real invoice) should return 200, not 500.
.venv/bin/python odoo-bin -c odoo17_dev.conf -d <db> -i activity_payment \
  --test-enable --test-tags /activity_payment --stop-after-init \
  --http-port 8941 --gevent-port 8942
```

## References

- Related file: `security/sod-approval-checks.md`
- Related file: `misc/running-module-tests-demo-and-port-collisions.md`
- `odoo/addons/base/models/ir_http.py::_auth_method_public`
- `addons/account/models/account_move_line.py::_prepare_exchange_difference_move_vals`
