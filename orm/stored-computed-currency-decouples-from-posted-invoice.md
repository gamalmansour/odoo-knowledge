# A Stored Computed Currency Field Silently Decouples From Its Posted Invoice

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `currency`, `multi-currency`, `invoice`, `account.move`, `computed-field`, `stored`, `money-integrity`, `state-machine`

---

## Problem

You make a record's `currency_id` a **stored computed** field derived from a related record (e.g. a subscription's currency computed from its schedule's city → country → currency), and you post an invoice (`account.move`) in that currency. Later, an admin changes the source relation (the schedule) on an **already-invoiced** record. The compute re-fires and silently flips the record's `currency_id` — while the posted invoice keeps its original currency.

```
sub.currency_id            == USD   # matches its posted out_invoice
sub.write({'schedule_id': eg_schedule})   # no error, no warning
sub.currency_id            == EGP   # flipped!
sub.invoice_id.currency_id == USD   # invoice unchanged
sub.amount_total (from the USD invoice) now displays labelled "EGP"
```

No exception is raised. The number is right; the currency label is wrong — a silent money-integrity bug that a passing test suite and a green install will not catch.

## Root Cause

`@api.depends`-driven recompute is **state-agnostic**: it recomputes whenever a dependency changes, regardless of the record's lifecycle state. A posted invoice freezes its currency, but the *source* record's stored computed currency keeps tracking the live relation. Freezing the *price* on confirm (a common pattern) does **not** freeze the currency, because currency is a separate computed field with its own depends chain.

## Solution ✅

Lock the money basis once it is committed. Add a `write()` (or `@api.constrains`) guard that blocks changing the currency-determining relation after draft:

```python
def write(self, vals):
    if 'schedule_id' in vals:
        new = vals['schedule_id'] or False
        locked = self.filtered(
            lambda s: s.state != 'draft' and (s.schedule_id.id or False) != new)
        if locked:
            raise UserError(_(
                'The schedule of a confirmed subscription cannot be changed — '
                'cancel it (or use renew) and create a new one.'))
    return super().write(vals)
```

Mirror it in the view so the UI matches the model rule:

```xml
<field name="schedule_id" readonly="state != 'draft'"/>
<field name="month_id"    readonly="state != 'draft'"/>
```

Also make the compute defensive so `currency_id` is **never empty or inactive** (a Monetary/invoice needs an active currency):

```python
@api.depends('schedule_id.currency_id', 'company_id.currency_id')
def _compute_currency_id(self):
    for rec in self:
        cur = rec.schedule_id.currency_id
        rec.currency_id = cur if (cur and cur.active) else rec.company_id.currency_id
```

## ⚠️ Pitfalls

- **Don't guard only the price.** Freezing `unit_price` on confirm feels like enough — it isn't. Currency is a separate field; guard the *relation* that drives both.
- **Guard on a real change, not on every write.** Compare `(rec.field.id or False) != new` so Odoo's full-record re-write (webclient sends all fields) and idempotent same-value writes don't false-positive. Also block clearing to `False`.
- **Foreign-currency invoicing on a single company works** — `account.move` with a `currency_id` ≠ company base posts fine; tax and income accounts are company-scoped, not currency-scoped. But: activate the currency (`res.currency.active`) and seed a `res.currency.rate`, else Odoo values it 1:1 in company books (core `_get_rates` COALESCEs to 1.0) — log a warning on a missing rate.
- **Fixed-amount coupons/discounts are currency-less Floats.** Under multi-currency they mean "50" in whatever currency the record resolves to (50 SAR vs 50 EGP) — decide and document (percent stays currency-safe).

## Verification

```python
sub = confirm_and_invoice(...)        # posts an out_invoice in USD
before = sub.currency_id
with self.assertRaises(UserError):
    sub.write({'schedule_id': egp_schedule})
self.assertEqual(sub.currency_id, before)                 # unchanged
self.assertEqual(sub.invoice_id.currency_id, before)      # still matches
```

## References

- **General pattern:** `orm/freeze-stored-money-across-lifecycle-snapshot-and-lock-not-state-skip.md` — same core lesson (write-lock the basis fields once the record leaves Draft). This entry is the **currency/invoice specialization**: the failure isn't a zeroed value but a *mislabelled* one (currency flips vs a posted `account.move`), and it adds the multi-currency-invoicing-on-a-single-company facts + the fixed-coupon-currency pitfall.
- Related file: `orm/onchange-only-computation-breaks-nonform-create.md` (compute-in-a-helper discipline)
- Odoo core: `account/models/account_move.py` (currency on posted moves), `base/models/res_currency.py::_get_rates` (identity-1.0 fallback)
