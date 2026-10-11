# `skip_backorder=True` Still CREATES the Backorder — It Only Skips the Wizard

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm / stock                                |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `stock.picking`, `button_validate`, `backorder`, `skip_backorder`, `picking_ids_not_to_backorder`, `partial-delivery`

---

## Problem

Automated code validates a partially-delivered picking with:

```python
picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
```

expecting "no backorder". The validation goes through silently (no wizard) — but a **backorder picking IS created** for the undelivered remainder. In a vehicle-delivery flow this backorder is a pending outgoing picking sourced from the VEHICLE's transit location, which downstream "latest pending picking" fallbacks then wrongly pick up for future visits of the same sale order.

## Root Cause

Two DIFFERENT context keys control two different things in `stock.picking.button_validate`:

- `skip_backorder=True` → only suppresses the **backorder confirmation WIZARD**; Odoo then applies its DEFAULT resolution, which is **create the backorder**.
- `picking_ids_not_to_backorder=[ids]` → the pickings whose remainder must be **cancelled instead of backordered** (`stock/models/stock_picking.py` reads it explicitly).

Passing only the first is the trap: it silences the question and answers "yes, backorder" on your behalf.

## Solution ✅

```python
picking.with_context(
    skip_backorder=True,
    skip_sms=True,
    picking_ids_not_to_backorder=picking.ids,
).button_validate()
```

Result: picking done, remaining demand cancelled, `qty_delivered` reflects reality, and **no pending picking is left behind**.

## ⚠️ Pitfalls

- **Decide the business consequence first:** with no backorder the undelivered remainder is gone — delivering it later needs a new order/transfer. If the flow SHOULD deliver later, the backorder was correct and the fix is routing it properly, not suppressing it.
- **Billing mismatch:** if invoices are generated from ORDERED quantities at order confirmation, a partial delivery leaves the (draft) invoice larger than what was delivered — the remainder cancellation does not fix billing by itself.
- Physically, in vehicle flows, the undelivered goods stay in the vehicle's transit location until an unload transfer returns them to the warehouse.
- Assert the negative in tests: `search([('backorder_id', '=', picking.id)])` must be empty AND no pending outgoing picking remains on the order.

## Verification

`sale_visit` partial-delivery flow (Odoo 19): before the fix a backorder appeared after every supervisor-approved partial delivery; after adding `picking_ids_not_to_backorder`, test asserts done picking + zero backorders + `qty_delivered` = delivered qty + no pending pickings (48/48 module tests green).

## References

- Core: `odoo/addons/stock/models/stock_picking.py` (`picking_ids_not_to_backorder`, `skip_backorder`)
- Fixed file: [sale_visit/models/sale_visit.py](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/models/sale_visit.py) `_validate_delivery_picking`
