# Splitting Outgoing Deliveries or Incoming Receipts Across Multiple Warehouses (Wizard Pattern)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / stock                                |
| Odoo Versions | 19 (pattern applies to 16+)                |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.picking`, `multi-warehouse`, `split`, `wizard`, `sale_line_id`, `purchase_line_id`, `price_unit`, `action_assign`, `operation-type`

---

## Problem

Distribution & purchasing flow: a Sale Order's delivery (`outgoing`) or a Purchase Order's receipt (`incoming`) is issued on a single warehouse, and the warehouse manager needs to route specific lines—or split a single product's quantity—across multiple physical warehouses. One `stock.picking` has one `picking_type_id` and one source/destination location, so splitting across warehouses requires creating separate transfers per warehouse while preserving full SO/PO linkage and valuation.

## Solution ✅

A wizard on the picking ("Split by Warehouse", visible when `picking_type_code in ('outgoing', 'incoming')` and `state not in ('done', 'cancel')`) with:
- a **document-level warehouse** field (one entry applies to all lines — mandatory UX for 100-line documents; also replaces the manual operation-type edit),
- per-line warehouse override,
- quantity split (a second wizard line for the same product with the rest of the quantity + another warehouse), validated so per-product quantities equal the move's demand exactly (`float_compare` with the uom rounding).

Direction-aware routing (`_get_warehouse_operation_and_location`):
- **Outgoing (`picking_type_code == 'outgoing'`)**: uses `warehouse.out_type_id` and updates `location_id` (`warehouse.out_type_id.default_location_src_id or warehouse.lot_stock_id`), keeping `location_dest_id` (customer) unchanged.
- **Incoming (`picking_type_code == 'incoming'`)**: uses `warehouse.in_type_id` and updates `location_dest_id` (`warehouse.in_type_id.default_location_dest_id or warehouse.lot_stock_id`) plus `location_final_id = warehouse.lot_stock_id.id` on `stock.move`, keeping `location_id` (supplier) unchanged.

Apply algorithm (order matters):
1. Reset `picked = False` on active moves and move lines, then call `picking.do_unreserve()` FIRST — quantities and locations change next.
2. Group `(move, qty)` per target warehouse. The original document is kept for the document-level warehouse (never left empty — fall back to the largest group).
3. Other groups → `picking.copy({'move_ids': [], 'move_line_ids': [], 'picking_type_id': ..., 'location_id': ..., 'location_dest_id': ..., ...})`; whole-demand moves are re-parented (`move.write(...)`), partial quantities reduce the original move and `move.copy(...)` — **explicitly carrying `sale_line_id`, `purchase_line_id`, `price_unit`, `warehouse_id`, and `location_final_id`**.
4. Retype the original when its target differs (write `picking_type_id` + location on picking AND its moves).
5. `created.action_confirm()` then **guarded** reserve (`action_assign()`).

## ⚠️ Pitfalls

- **`stock.move.price_unit` is `copy=False` in core `stock`**: When splitting a move's quantity via `move.copy({...})`, you MUST explicitly pass `'price_unit': move.price_unit` (along with `'purchase_line_id': move.purchase_line_id.id` and `'sale_line_id': move.sale_line_id.id`). Forgetting `price_unit` causes the split purchase receipt move to be valued at `0.0`, corrupting AVCO/FIFO inventory valuation.
- **Odoo 19 `_do_unreserve()` skips moves with `move.picked == True`**: Always clear `picked = False` on active moves and move lines before calling `picking.do_unreserve()`, otherwise move lines remain attached to the old picking/location.
- **Update `warehouse_id` and `location_final_id` on `stock.move` for incoming receipts**: `purchase.order.line._prepare_stock_move_vals` sets `warehouse_id` and `location_final_id` on `stock.move`. In Odoo 19, `stock.move._compute_location_dest_id` forces `location_dest_id = move.location_final_id` when `location_final_id` is set, and push rules check `move.warehouse_id`. Always update both fields to match the target warehouse.
- **`action_assign()` raises `UserError: Nothing to check the availability for.`** when every move is already reserved — outgoing types often auto-reserve on confirm. Guard it: only call when `move_ids.filtered(lambda m: m.state in ('confirmed', 'partially_available'))` is non-empty.
- **`%(action_xmlid)d` in a button requires the action record to be defined ABOVE the view in the same XML file** — same-file load order, see [external_id_not_found_parse_error](../views/external_id_not_found_parse_error.md).
- Keep the **procurement group / origin** on the copied picking (`picking.copy` preserves `origin`) and `purchase_line_id`/`sale_line_id` on the moves — `purchase.order.picking_ids` is computed from `order_line.move_ids.picking_id`.

## Verification

Module `stock_picking_warehouse_split` (`19.0.1.1.0`): 9 tests covering both outgoing SO deliveries and incoming PO receipts (prefill, whole-line reroute, quantity split with `qty_received` & `price_unit` verification, document-level retype without extra picking, demand-mismatch block, done-picking block).

## References

- Module: [custom/stock_picking_warehouse_split](file:///Users/gamal/odoo/odoo19.0/custom/stock_picking_warehouse_split/)

