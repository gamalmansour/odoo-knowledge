# Seeding Realistic Demo Transactions from Backend Scripts (PO/SO/POS Sessions) — Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19 (verified on 19)                |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-07-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `demo-data`, `pos.order`, `pos.session`, `sale.order`, `purchase.order`, `backdating`, `seeding`, `reports`

---

## Problem

For a client demo you need REAL report data (P&L, aged receivable, sales analysis, POS
dashboards): confirmed POs with receipts and bills, delivered+invoiced SOs with partial payments,
and CLOSED pos.sessions with their accounting entries — all backdated over ~3 months. Creating
POS orders from the backend is undocumented and easy to get wrong (amounts stay 0, sessions
won't close).

## Solution ✅

Copy the official pattern from `addons/point_of_sale/tests/common.py` (`create_backend_pos_order`):

```python
config.open_ui()                              # creates the session
session = config.current_session_id
order = env['pos.order'].create({
    'company_id': env.company.id, 'session_id': session.id,
    'date_order': some_past_datetime,          # backdate freely
    'amount_total': 0, 'amount_paid': 0, 'amount_tax': 0, 'amount_return': 0,
    'lines': [(0, 0, {'product_id': p.id, 'qty': qty, 'price_unit': p.lst_price,
                      'price_subtotal': p.lst_price * qty, 'price_subtotal_incl': 0,
                      'tax_ids': [(6, 0, p.taxes_id.ids)]})],
})
order.lines._onchange_amount_line_all()        # ← without these two the amounts stay wrong
order._compute_prices()
ctx = {'active_ids': order.ids, 'active_id': order.id}
env['pos.make.payment'].with_context(**ctx).create(
    {'payment_method_id': pm.id, 'amount': order.amount_total}).with_context(**ctx).check()
# after all orders:
session.post_closing_cash_details(total_cash_paid_in_session)
session.close_session_from_ui()                # posts the session journal entries
```

Backdating rules learned the hard way:
- `sale.order.action_confirm()` OVERWRITES `date_order` with now() — write the date AFTER confirm.
- `purchase.order`: write `date_order` + `date_approve` after `button_confirm()`.
- Pickings: set per-move `move.quantity = move.product_uom_qty; move.picked = True` then
  `button_validate()`, then write `date_done` (writable post-done).
- Invoices/bills: write `invoice_date` AND `date` before `action_post()`.
- Payments: `account.payment.register` wizard accepts `payment_date`.

Other essentials:
- Run as the admin user (`env(user=env.ref('base.user_admin').id)`), NOT shell superuser/OdooBot —
  salesperson/cashier fields end up presentable in reports.
- `env.cr.commit()` per document loop as a checkpoint; stamp `origin='DEMO-SEED'` for idempotent
  re-runs and easy cleanup.
- `random.seed(N)` keeps re-runs deterministic.

## ⚠️ Pitfalls

- Skipping `_onchange_amount_line_all()` + `_compute_prices()` leaves order totals at 0 and the
  payment wizard pays 0 — the session then fails to close with a difference.
- `post_closing_cash_details()` expects the COUNTED cash = opening balance + cash payments of
  that session; pass the sum of cash-method payments you actually created.
- Cash vs bank methods: filter `config.payment_method_ids` by `is_cash_count` — do not hardcode.
- Backend-created POS orders do NOT apply loyalty/promotion programs (those are UI-side) — fine
  for seeding, but don't expect promo lines in the seeded history.
