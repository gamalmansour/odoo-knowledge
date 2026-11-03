# Employee Custody Location Auto-Switch, Quant Re-Reservation, and Odoo 19 Return/Repair Location Traps

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.picking`, `stock.return.picking`, `repair.order`, `hr.employee`, `custody-location`, `web_read`

---

## Problem

When field engineers or van sales/maintenance technicians are assigned a dedicated internal custody stock location (e.g., `NCW/MEKKAWY - VAN N300` or `NCW/Maintenance Warehouse`) and must ONLY issue goods from and receive customer returns/repairs into their assigned location, three critical Odoo 19 traps break naive location restrictions:

1. **Sales Order Confirmation Trap (`WH/Stock` Reservation):** Sales Orders are typically confirmed by a salesperson or back-office user, which creates the `outgoing` `stock.picking` (`WH/OUT/xxxxx`) and reserves `stock.quant` rows on the main warehouse location (`WH/Stock`). If you only override `default_get` or `create` on `stock.picking`, the delivery remains on `WH/Stock`, or if you block `button_validate`, the engineer is locked out of every Sales Order delivery.
2. **Odoo 19 Customer Return Trap (`stock.return.picking`):** In Odoo 19 (`addons/stock/wizard/stock_picking_return.py`), `_prepare_picking_default_values_based_on()` contains:
   ```python
   if return_type and return_type.code == 'incoming':
       location_dest = return_type.default_location_dest_id
   else:
       location_dest = picking.location_id
   ```
   Because `out_type_id.return_picking_type_id` is the `incoming` Receipts operation type whose `default_location_dest_id` is `WH/Stock`, returning a delivery from a Van (`NCW/MEKKAWY - VAN N300`) silently routes the returned goods to `WH/Stock` instead of the engineer's Van!
3. **Odoo 19 `repair.order` Hidden Location Trap:** In Odoo 19 (`addons/repair/views/repair_views.xml`), `location_id` (parts source) and `recycle_location_id` are omitted from `repair.view_repair_order_form` and computed from `picking_type_id.default_location_src_id` (`WH/Stock`). Maintenance engineers unknowingly pull spare parts from `WH/Stock` instead of their Maintenance Warehouse.

## Root Cause

- Procurement rules (`stock.rule`) bind the `stock.picking` source location at Sales Order confirmation time using the warehouse's `lot_stock_id`.
- `stock.return.picking._prepare_picking_default_values_based_on` prioritizes `return_type.default_location_dest_id` whenever `return_type.code == 'incoming'`.
- `repair.order` computes `location_id`, `recycle_location_id`, `product_location_src_id`, and `product_location_dest_id` from `picking_type_id` without exposing `location_id` on the form view.

## Solution ✅

1. **Link `default_stock_location_id` on `hr.employee` (and `hr.employee.public`)** and resolve it via a helper on `res.users` (`_get_solargy_default_stock_location(company)`), always returning an empty recordset for `self._is_superuser()` so cron jobs are never blocked.
2. **Auto-Switch & Re-Reserve on Single-Record Form Open (`web_read` when `len(self) == 1`) and `button_validate`:**
   - When a restricted engineer opens an open (`state not in ('done', 'cancel')`) outgoing delivery in Form view (`len(self) == 1` in `web_read`), unreserve any moves reserved on `WH/Stock` (`moves_wrong_loc.sudo()._do_unreserve()`), update `picking.location_id`, `move_ids.location_id`, and `move_line_ids.location_id` to `user_loc`, and call `action_assign()` to reserve from the engineer's custody location.
   - Lock `location_id`, `location_dest_id`, and `picking_type_id` as `readonly` in the UI using a non-stored computed boolean `is_user_location_locked`, backed by `write()` and `button_validate()` checks.
3. **Override `stock.return.picking._prepare_picking_default_values_based_on` Conditionally:**
   - If the current user has a restricted `user_loc`, force `vals['location_dest_id'] = user_loc.id` on returns of outgoing pickings and lock `location_dest_id` on the resulting return picking.
   - If the current user is an unrestricted user (Accounting / Warehouse manager), leave `vals` untouched and `is_user_location_locked = False` so they can freely choose or correct the return destination.
4. **Enforce and Expose `location_id` & `recycle_location_id` on `repair.order`:**
   - Override `_compute_location_id`, `_compute_recycle_location_id`, `_compute_product_location_src_id`, `_compute_product_location_dest_id`, `web_read`, `create`, `write`, and `_action_repair_confirm` / `action_repair_done` on `repair.order` so `add` moves consume from `user_loc` and `recycle` moves return to `user_loc`.

## ⚠️ Pitfalls

- **Never run auto-switch when `len(self) > 1` in `web_read` or `read`:** List views read batches of records; auto-switching on batch read would steal every open delivery order in the company as soon as an engineer opens the Delivery Orders list view. Restrict `web_read` auto-switching strictly to `len(self) == 1`.
- **Always call `_do_unreserve()` before changing `move.location_id`:** Changing `stock.move.location_id` without unreserving existing `stock.move.line` records leaves `stock.quant.reserved_quantity` stranded in `WH/Stock`.

## Verification

```bash
./odoo-bin -c solargy.conf -d solargy -u solargy_stock_user_location --test-enable --test-tags /solargy_stock_user_location --stop-after-init
```

## References

- Related file: `orm/auto-validate-returns-transit-location.md`
