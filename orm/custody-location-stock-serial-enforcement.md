# Custody Location Enforcement: Preventing Cross-Warehouse Serial Selection & Negative Stock on Delivery/Repair Validation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-21                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock`, `stock.picking`, `stock.move.line`, `stock.quant`, `serial-number`, `lot_id`, `custody-location`, `repair.order`

---

## Problem

When field/van engineers are bound to a dedicated internal custody location (`default_stock_location_id`, e.g., `NCW/MEKKAWY - VAN N300`), locking `picking.location_id` alone is NOT enough to prevent stock and serial-number corruption when Warehouse has not yet transferred the physical unit to the engineer's van:

1. **Silent Main-Warehouse Serial Pull / Negative Custody Stock:** When a Sales Order is confirmed by Sales, Odoo reserves a FIFO serial number from `NCW/Main`. If the engineer validates directly (or forces `quantity`), or selects that serial number via `lot_ids` on the Operations tab (`domain="[('product_id','=',product_id)]"` has no location filter), Odoo allows issuing a serial that is still sitting in `NCW/Main` — creating a negative quant in the engineer's van while leaving the real serial stranded in `NCW/Main` (or delivering the wrong serial from `NCW/Main`).
2. **`stock.quant._gather()` False Positive on Lot Checks:** Calling `stock.quant._gather(product, user_loc, lot_id=lot)` in Odoo 19 generates `Domain('lot_id', 'in', [lot_id.id, False])`, which silently includes untracked quants (`lot_id = False`) in the result!
3. **`stock.quant.available_quantity` False Block on Self-Reserved Moves:** Checking `available_quantity >= needed` inside `button_validate()` falsely blocks valid deliveries when the current picking itself holds the reservation (`quantity = 1, reserved_quantity = 1 → available_quantity = 0`).

## Root Cause

- `stock.move.line.create()` is invoked by `stock.move._set_lot_ids()` and UI Detailed Operations; guarding only `stock.move.line.write()` leaves `create()` unprotected.
- `preserve_demand_qty=True` during location switching on `button_validate()` can fabricate unbacked move lines (`move.quantity = target_qty`) when `action_assign()` found `0` stock in the custody location.
- `_gather()` intentionally includes `lot_id = False` to allow untracked quant compensation in Odoo core.

## Solution ✅

1. **Query exact physical on-hand in `child_of user_loc` via batched `stock.quant._read_group()`** (never `_gather()` for strict lot presence, and compare against physical `quantity`, not `available_quantity`, so self-reserved moves pass cleanly):

```python
prod_groups = self.env['stock.quant'].sudo()._read_group(
    [
        ('product_id', 'in', product_ids),
        ('location_id', 'child_of', user_loc.id),
    ],
    ['product_id'],
    ['quantity:sum'],
)
lot_groups = self.env['stock.quant'].sudo()._read_group(
    [
        ('product_id', 'in', product_ids),
        ('lot_id', 'in', lot_ids),
        ('location_id', 'child_of', user_loc.id),
    ],
    ['product_id', 'lot_id'],
    ['quantity:sum'],
)
```

2. **Enforce on BOTH `stock.move.line.create()` & `write()`** for outgoing deliveries and repair `add` moves (never customer returns or `recycle` moves!): reject `location_id != user_loc.id` and immediately reject any `lot_id` with `quantity <= 0` in `user_loc` — querying internal quants to report the serial's actual location (e.g., `NCW/Main`) in the `UserError`.
3. **Never force `move.quantity` above custody on-hand** when re-applying `user_loc` in `button_validate()`, and run `_solargy_check_custody_availability()` right before `super().button_validate()` (outgoing pickings) and `super().action_repair_done()` (`add` storable moves only).
4. **Handle Odoo 19 `picked` vs partial-delivery semantics cleanly:**
   - If `any(m.picked)` → validate `picked` storable moves with `quantity > 0`.
   - Else if any storable move has `quantity > 0` → validate those (allows valid partial deliveries / backorders).
   - Else (all storable moves have `quantity == 0`) → check `product_uom_qty` against `user_loc` on-hand so an empty-van engineer gets a clear custody-shortage error instead of Odoo's generic "no quantities done" message.

## ⚠️ Pitfalls

- **Do NOT apply on-hand / lot-presence checks to Customer Returns (`incoming` customer returns) or Repair `recycle` moves:** the returned/recycled serial is coming *into* `user_loc` and is not yet on hand there.
- **Do NOT check `repair.product_id` (the customer's unit being repaired) for custody on-hand:** only check `repair.move_ids` where `repair_line_type == 'add'` and `product_id.is_storable`.
- **Also handle `ml.lot_name` (string) when `ml.lot_id` is empty** on picking types where `use_create_lots=True` (such as `Repairs`).
- **Always convert quantities to `product.uom_id`** before comparing with `stock.quant.quantity`, using `product.uom_id.compare(avail, needed) < 0`.

## Verification

```bash
./odoo-bin -c solargy.conf -d solargy -u solargy_stock_user_location --test-enable --test-tags /solargy_stock_user_location --stop-after-init
```

## References

- Related module: `solargy_stock_user_location` (`models/stock_picking.py`, `models/repair_order.py`, `tests/test_stock_user_location.py`)
- Odoo 19 core: `addons/stock/models/stock_quant.py` (`_get_gather_domain`), `addons/stock/models/stock_move.py` (`_set_lot_ids`)
