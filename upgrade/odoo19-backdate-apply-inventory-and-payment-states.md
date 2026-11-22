# Odoo 19 Breaking Changes in Third-Party Backdate Modules (`_apply_inventory(date=None)`, `stock.move.name`, `account.payment.state`)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.quant`, `_apply_inventory`, `stock.move`, `account.payment`, `backdate`, `sql_injection`, `odoo19`

---

## Problem

Ported backdate suites (such as `sh_all_in_one_backdate_adv`) fail hard on Odoo 19 with multiple runtime crashes and security/accounting regressions:
1. Every Inventory Adjustment crashes with `TypeError: StockQuant._apply_inventory() takes 1 positional argument but 2 were given` — even when backdating is disabled.
2. Scrap backdating crashes with `AttributeError: 'stock.move' object has no attribute 'name'`.
3. Payment backdate wizards check legacy `'posted'`/`'cancel'` states, causing confirmed (`in_process`/`paid`) payments to fall into `else:`, wiping `payment.name` and desynchronizing `account.payment.date` from `payment.move_id.date`.
4. Unparameterized `cr.execute("... '%s' ..." % (...))` / f-string updates on `product_value` expose SQL injection and skip `flush_model()`/`invalidate_model()`.
5. Wizard fields using `default=datetime.now()` freeze defaults to server boot timestamp.

## Root Cause

- In Odoo 19 (`addons/stock/models/stock_quant.py:996`), `_apply_inventory(self, date=None)` accepts a `date` argument passed by `action_apply_inventory()`.
- In Odoo 19 (`addons/stock/models/stock_move.py:19`), `stock.move.name` was removed (`_rec_name = 'reference'`).
- In Odoo 19 (`addons/account/models/account_payment.py:36-43`), payment states are `draft`, `in_process`, `paid`, `canceled`, `rejected` (no `posted` or `cancel`).

## Solution ✅

1. **Fix `_apply_inventory` signature and forward `date`:**
```python
def _apply_inventory(self, date=None):
    if not self.env.company.backdate_for_inventory_adj:
        return super()._apply_inventory(date=date)
    backdate_quants = self.filtered(lambda x: x.sh_backdate)
    for quant in backdate_quants:
        super(
            StockQuant,
            quant.with_context(
                sh_backdate=quant.sh_backdate,
                sh_backdate_remark=quant.remarks_for_inventory_adj,
            ),
        )._apply_inventory(date=quant.sh_backdate)
        quant.inventory_date = quant.sh_backdate
    remaining = self - backdate_quants
    if remaining:
        return super(StockQuant, remaining)._apply_inventory(date=date)
```

2. **Use `move.move_line_ids`** instead of `search([('move_id', 'in', rec.name)])` on `stock.move`.
3. **Use Odoo 19 payment states** (`in_process`, `paid`, `canceled`, `rejected`) and preserve legal `name` sequence numbers while checking `inalterable_hash` and `_check_fiscal_lock_dates()`.
4. **Always parameterize SQL and synchronize ORM cache:**
```python
self.env['product.value'].flush_model()
self.env.cr.execute(
    "UPDATE product_value SET date = %s, create_date = %s WHERE id IN %s",
    (target_dt, target_dt, tuple(product_values.ids)),
)
self.env['product.value'].invalidate_model(['date', 'create_date'])
```
5. **Load `*_groups.xml` BEFORE `ir.model.access.csv`** in `__manifest__.py` when restricting wizard ACLs to dedicated backdate groups.

## ⚠️ Pitfalls

- Never mutate the shared `vals` dict inside `for rec in self:` in `stock.move.write()` or `stock.picking.write()` — copy `dict(vals)` per record and skip via a context guard (`sh_skip_backdate_sync=True`) during wizard updates.
- Never `return super().write(vals)` inside `for rec in self:` (exits after the first record and returns `None` on empty recordsets).
- Never use `default=datetime.now()` (evaluated once at import); pass the callable `default=fields.Datetime.now`.

## Verification

```bash
./odoo-bin -c custom.conf -d <db> -u sh_all_in_one_backdate_adv --stop-after-init
```
Verify Inventory Adjustment applies without `TypeError`, wizard defaults reflect current time, and `res_company.backdate_for_purchase_stock_move` is independent of `backdate_for_stock_move`.

## References

- Core `stock.quant`: `addons/stock/models/stock_quant.py`
- Core `account.payment`: `addons/account/models/account_payment.py`
