# POS Kit (Phantom BoM) Sale Crashes with MissingError on stock.move Post-Explosion

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pos`, `mrp`, `kit`, `phantom-bom`, `stock.move`, `_action_confirm`, `MissingError`, `unlink`, `odoo_multi_channel_sale`

---

## Problem

When completing a Point of Sale (PoS) order containing a Kit product (BoM of type `phantom`), the synchronization fails and rolls back the order transaction with:

```text
User #2 deleted stock.move records with IDs: [1948]
WARNING odoo.http: Record does not exist or has been deleted. (Record: stock.move(1948,), User: 2)
odoo.exceptions.MissingError: Record does not exist or has been deleted.
(Record: stock.move(1948,), User: 2)
```

## Root Cause

In Odoo's MRP integration with inventory, kit products (`mrp.bom` with `type='phantom'`) do not move the kit product itself. Instead, during `stock.move._action_confirm()`:
1. `mrp` overrides `_action_confirm` and calls `self.action_explode()`.
2. `action_explode()` generates new `stock.move` records for each component of the kit.
3. It then cancels and **unlinks** the original parent `stock.move` record (`move_to_unlink.unlink()`).
4. `_action_confirm()` returns the new component moves (`moves`).

If any module (such as `odoo_multi_channel_sale` or custom integrations) overrides `_action_confirm()` or `_action_done()` and invokes post-processing on `self` without checking existence:

```python
# ❌ VULNERABLE CODE:
def _action_confirm(self, *args, **kwargs):
    res = super()._action_confirm(*args, **kwargs)
    self.post_operation(stock_operation='_action_confirm') # 'self' has been unlinked!
    return res
```

Accessing `move.product_id` (or any other field) on records in `self` raises `MissingError` because the original move ID has already been deleted from PostgreSQL.

## Solution ✅

Operate on the resulting recordset returned by `super()` rather than `self`, and defensively ensure records still exist with `.exists()`:

```python
# ✅ SAFE IMPLEMENTATION:
def _action_confirm(self, *args, **kwargs):
    res = super()._action_confirm(*args, **kwargs)
    moves = (res if isinstance(res, models.Model) else self).exists()
    if moves:
        moves.post_operation(stock_operation='_action_confirm')
    return res

def _action_done(self, **kwargs):
    res = super()._action_done(**kwargs)
    moves = (res if isinstance(res, models.Model) else self).exists()
    if moves:
        moves.post_operation(stock_operation='_action_done')
    return res

def _action_cancel(self, *args, **kwargs):
    cancelled = self.filtered(lambda sm: sm.state == 'cancel')
    res = super()._action_cancel(*args, **kwargs)
    moves = self.exists()
    if not cancelled and moves:
        moves.post_operation(stock_operation='_action_cancel')
    return res

def post_operation(self, stock_operation):
    initial_channel_ids = self.env['multi.channel.sale'].search([]).ids
    for move in self.exists():
        ...
```

## ⚠️ Pitfalls

- **Do NOT assume `self` remains intact across `_action_confirm`**: Always remember MRP kit mechanics hard-delete parent moves.
- **Components vs Kit Parent**: Post-processing (like channel quantity sync or tracking) should synchronize the exploded components that actually moved in stock, which are returned in `res`, not the deleted kit move.

## Verification

Create a PoS order containing a kit product and execute `_create_order_picking()` or sync from PoS UI:
The picking is created and transitioned to `done`, moving component quantities without raising `MissingError`.
