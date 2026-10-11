# Splitting One Outgoing Picking Across Several Source Warehouses (Wizard Pattern)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / stock                                |
| Odoo Versions | 19 (pattern applies to 16+)                |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.picking`, `multi-warehouse`, `split`, `wizard`, `sale_line_id`, `action_assign`, `operation-type`

---

## Problem

Distribution flow: every sale order's delivery is issued on an **intermediate warehouse**; the warehouse manager then manually changes each picking's operation type to the real source warehouse. When a FEW products of one picking must ship from a *different* warehouse (sometimes only part of one product's quantity), there is no standard way to split the document — one picking has one operation type and one source.

Note: Odoo 19's core `sale.order.line.warehouse_id` does NOT solve this — it is a **computed** field derived from the order/route at confirmation time, while here the decision is taken later, per picking, by the warehouse manager.

## Solution ✅

A wizard on the outgoing picking ("Split by Warehouse") with:
- a **document-level warehouse** field (one entry applies to all lines — mandatory UX for 100-line documents; also replaces the manual operation-type edit),
- per-line warehouse override,
- quantity split (a second wizard line for the same product with the rest of the quantity + another warehouse), validated so per-product quantities equal the move's demand exactly (`float_compare` with the uom rounding).

Apply algorithm (order matters):
1. `picking.do_unreserve()` FIRST — quantities and locations change next.
2. Group `(move, qty)` per target warehouse. The original document is kept for the document-level warehouse (never left empty — fall back to the largest group).
3. Other groups → `picking.copy({'move_ids': [], 'move_line_ids': [], 'picking_type_id': wh.out_type_id.id, 'location_id': src.id, ...})`; whole-demand moves are re-parented (`move.write({'picking_id': ..., 'picking_type_id': ..., 'location_id': ...})`), partial quantities reduce the original move and `move.copy(...)` — **explicitly carrying `sale_line_id`** so invoicing/qty_delivered/delivery smart-button stay correct.
4. Retype the original when its target differs (write picking_type + location on picking AND its moves).
5. `created.action_confirm()` then **guarded** reserve.

## ⚠️ Pitfalls

- **`action_assign()` raises `UserError: Nothing to check the availability for.`** when every move is already reserved — outgoing types often auto-reserve on confirm. Guard it: only call when `move_ids.filtered(lambda m: m.state in ('confirmed', 'partially_available'))` is non-empty. (Caught by the test suite, not by installation.)
- **`%(action_xmlid)d` in a button requires the action record to be defined ABOVE the view in the same XML file** — same-file load order, see [external_id_not_found_parse_error](../views/external_id_not_found_parse_error.md).
- Keep the **procurement group / origin** on the copied picking (`picking.copy` preserves `group_id`) — losing it detaches the new document from the SO's delivery count.
- Wizard UX: product choice on manually added rows needs a computed `allowed_product_ids` m2m on the wizard + `domain="[('id','in', parent.allowed_product_ids)]"` (same pattern as [scope-many2one-to-cross-model-set-with-computed-m2m-domain](../views/scope-many2one-to-cross-model-set-with-computed-m2m-domain.md)), plus an `@api.onchange('product_id')` resolving `move_id` — with an apply-time fallback for RPC callers.
- Downstream batch flows that assume "one batch = one warehouse" keep working because each resulting picking carries its own warehouse's operation type.

## Verification

Module `stock_picking_warehouse_split` (Odoo 19): 6 tests green on a copy of the production-test DB — prefill, whole-line reroute (sale linkage asserted), quantity split 30/20, document-level retype without extra picking, demand-mismatch block, done-picking block.

## References

- Module: [custom/stock_picking_warehouse_split](file:///Users/gamal/odoo/odoo19.0/custom/stock_picking_warehouse_split/)
