# Partial refund posted a FULL credit note (100% reversal) instead of a fraction — and the fix's own line filter silently produced a $0 note

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17 (display_type default applies to 16+)   |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `account.move`, `credit-note`, `out_refund`, `_reverse_moves`, `partial-refund`, `display_type`, `money-integrity`, `rounding`

---

## Problem

A refund-request workflow computes `amount` as a FRACTION of a paid invoice
(e.g. `paid × unattended_sessions / total_sessions`), but `action_approve`
called `invoice._reverse_moves([...])` — Odoo's own full-mirror reversal —
unconditionally. `_reverse_moves` always reproduces the ENTIRE original
invoice on the credit note; there is no "reverse X% of it" argument. Result:
a genuinely partial refund (e.g. `amount = 172.50` on a `230.00` invoice)
posted a credit note for the FULL `230.00` — a real over-refund, silent
(no error, no warning, the automated tests all happened to use 100%-refund
fixtures so the discrepancy never showed).

Fixing it by hand-building a NEW `out_refund` move from
`invoice.invoice_line_ids` with `price_unit` scaled by the fraction then hit
a SECOND, unrelated trap: every line came out with `amount_total == 0.0`.

## Root Cause

1. **The 100%-reversal bug**: `account.move._reverse_moves()` has no partial
   mode — it is architecturally "create a full mirror" (used correctly for
   voiding an invoice entirely, wrong for a genuinely fractional refund).
2. **The $0-line bug** (introduced while fixing #1): the natural-looking
   filter `invoice.invoice_line_ids.filtered(lambda l: not l.display_type)`
   silently excludes every real product line. `account.move.line.display_type`
   is a required, always-populated `Selection` (`_compute_display_type`,
   `precompute=True`) — a normal billable line's value is the STRING
   `'product'`, never `False`/empty. `not l.display_type` is therefore
   `not 'product'` → `False` for every real line, so the "exclude non-product
   lines" filter excludes the product lines themselves and keeps nothing.

## Solution ✅

Build the partial credit note from the ORIGINAL invoice's lines, scaling
`price_unit` by the refund fraction (taxes recompute naturally — a flat-rate
tax scaled pre-tax lands on the same post-tax fraction of the total, so
there's no separate "tax the total" formula to keep in sync):

```python
def _partial_credit_note(self, invoice, factor, expected_amount, reason=None):
    # invoice_line_ids' own field domain is already
    # [('display_type', 'in', ('product', 'line_section', 'line_note'))] —
    # filter DOWN to 'product' specifically; section/note lines carry no
    # price and must never become billable lines on the note.
    lines = [(0, 0, {
        'name': line.name,
        'quantity': line.quantity,
        'price_unit': line.price_unit * factor,
        'account_id': line.account_id.id,
        'tax_ids': [(6, 0, line.tax_ids.ids)],
        'analytic_distribution': line.analytic_distribution or False,
    }) for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product')]

    credit_note = self.env['account.move'].with_company(invoice.company_id).create({
        'move_type': 'out_refund',
        'partner_id': invoice.partner_id.id,
        'company_id': invoice.company_id.id,
        'currency_id': invoice.currency_id.id,
        'reversed_entry_id': invoice.id,   # links it in the UI, same as _reverse_moves does
        'invoice_line_ids': lines,
    })

    # Money-safety guard: never post a note that doesn't match the amount
    # the caller was actually promised — unlink the still-DRAFT note and
    # raise instead of posting a silently wrong number.
    tolerance = credit_note.currency_id.rounding or 0.01
    if abs(credit_note.amount_total - expected_amount) > tolerance:
        note_total = credit_note.amount_total
        credit_note.unlink()
        raise UserError(_('Credit note total (%s) != expected (%s).', note_total, expected_amount))

    credit_note.action_post()
    return credit_note
```

Keep the ORIGINAL `_reverse_moves()` full-mirror path for genuine
100%-void-this-invoice flows (e.g. plain cancel) — don't replace it, just
never reuse it for a fractional refund.

## ⚠️ Pitfalls

- `not line.display_type` is ALWAYS False for a real invoice line in 16+ —
  it looks like an "exclude system/blank lines" filter but silently excludes
  everything. Filter FOR `display_type == 'product'`, never `not display_type`.
- Independent rounding paths (Python-side `currency.round()` for the
  "expected" amount vs. Odoo's own per-line subtotal+tax rounding on the
  note) can differ by exactly one cent on non-clean fractions (e.g. 2/3).
  Use a tolerance of `currency.rounding`, not an exact `==` comparison — but
  DO keep the tolerance check (don't drop it "to make tests pass"); a
  genuine mismatch (wrong factor, stale invoice lines) must still raise.
- `reversed_entry_id` is `readonly=True` on the field — that only blocks
  the UI form, not ORM `create()`/`write()`; it's fine (and expected) to set
  it directly when hand-building the note.
- A 100%-refund case (`factor=1.0`) should be regression-tested too — the
  scaled-line builder must land EXACTLY on the full invoice total in that
  case, proving the fix didn't just move the bug rather than close it.

## Verification

```python
# Regression: cost 200 + 15% VAT -> paid 230; unattended 3/4 -> refund.amount
# = 172.5. The posted note must total 172.5, NEVER 230.
self.assertEqual(credit_note.amount_total, 172.5)
self.assertNotEqual(credit_note.amount_total, 230.0)
```

## References

- Related file: `security/sod-approval-checks.md`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- `addons/account/models/account_move.py::invoice_line_ids` (the domain),
  `addons/account/models/account_move_line.py::display_type` (the selection)
