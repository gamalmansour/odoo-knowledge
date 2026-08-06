# Seeding Realistic Demo Transactions from Backend Scripts (PO/SO/POS Sessions) — Odoo 19

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19 (verified on 19)                |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-08-06                                 |
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

## 🏭 MRP addendum (verified 2026-08-06 on Odoo 18, anwar_factory demo)

Manufacturing orders CANNOT be backdated through the ORM after completion —
`mrp.production.write()` raises *"You cannot move a manufacturing order once it is
cancelled or done"* for `date_start`/`date_finished`. Backdate with SQL after
`button_mark_done()`:

```python
env.cr.execute("UPDATE mrp_production SET date_start=%s, date_finished=%s WHERE id=%s",
               (d_start, d_done, mo.id))
env.cr.execute("UPDATE stock_move SET date=%s WHERE id IN %s AND state='done'",
               (d_done, tuple((mo.move_raw_ids | mo.move_finished_ids).ids)))
# same UPDATE for stock_move_line (move_id IN ...)
```

MO completion recipe that works with mrp_workorder (enterprise) installed:
`action_confirm()` → `action_assign()` → loop `workorder_ids`: `button_start()` +
`button_finish()` (wrap in try/except) → `qty_producing = qty` → per raw move
`quantity = product_uom_qty; picked = True` → `button_mark_done()` (handle a returned
wizard dict via `env[res['res_model']].with_context(**res['context']).create({}).process()`).

Opening stock: `env['stock.quant'].with_context(inventory_mode=True).create({...,
'inventory_quantity': q}).action_apply_inventory()` — quants in child locations are
found by parent-location reservations, so seed sub-locations freely. Negative quants
at *Virtual Locations/Inventory adjustment*, */Production* and *Partners/Vendors* are
NORMAL counterparts, not data corruption — only `usage='internal'` negatives are bugs.

Two more pitfalls found on a live seed:
- **Pricelist keeps the old currency after switching localization.** Loading a chart
  template (`account.chart.template.try_loading('sa', company)`) flips the company to
  SAR but the default `product.pricelist` (created at DB creation in USD) is NOT
  updated → every SO and its invoices come out in USD while vendor bills are SAR. Fix
  the pricelist currency BEFORE seeding; if documents already exist and no
  `res.currency.rate` rows exist (1:1), relabeling `currency_id` via SQL on
  `sale_order(_line)`, `account_move(_line)`, `account_payment`,
  `account_partial_reconcile.debit/credit_currency_id` is safe.
- **Raw-SQL writes are invisible to a running server.** `UPDATE res_partner SET
  lang=...` via psql does not invalidate the ormcache of an already-running Odoo
  process (user context, assets). Do user/lang/currency changes through the ORM in
  `odoo-bin shell` (signaling invalidates other processes), and remember the web
  session keeps its login-time lang until the user re-logs or changes Preferences.
