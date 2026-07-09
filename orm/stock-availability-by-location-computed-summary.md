# System-Wide Stock Availability by Location as a Computed Text Summary

**Category:** ORM
**Tags:** #orm, #stock, #stock.quant, #compute, #inventory, #ux
**Severity:** 🟢 Low
**Last Verified:** 2026-07-09
**Odoo Versions:** 17

## Problem
On a document line that references a `product.product` (here: a material
requisition line), the user wants an at-a-glance answer to "is this product
available anywhere in the system, and where?" — across ALL warehouses/locations,
not scoped to the current project/company context, without leaving the row.

## Solution ✅
A non-stored computed `Text` field on the line, depending only on `product_id`,
querying `stock.quant` directly (not `qty_available` on the product, which is
context-scoped to a single location/warehouse and won't give the full
system-wide breakdown):

```python
@api.depends('product_id')
def _compute_stock_availability(self):
    for rec in self:
        product = rec.product_id
        if not product:
            rec.stock_availability = False
            continue
        if product.detailed_type != 'product':
            rec.stock_availability = _('Consumable — not stock-tracked (always available to order).')
            continue
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal'),
        ])
        by_location = {}
        for quant in quants:
            free_qty = quant.quantity - quant.reserved_quantity
            if free_qty <= 0:
                continue
            by_location[quant.location_id] = by_location.get(quant.location_id, 0.0) + free_qty
        rec.stock_availability = (
            _('Not available in any warehouse/location.') if not by_location else
            ' | '.join('%s: %s %s' % (loc.display_name, round(qty, 2), product.uom_id.name)
                       for loc, qty in sorted(by_location.items(), key=lambda kv: -kv[1]))
        )
```

Key correctness points:
- **Free qty, not on-hand qty**: `quantity - reserved_quantity` per quant. Showing
  raw `quantity` would tell the user stock exists when it's actually fully
  committed elsewhere (reserved for other pickings) — misleading for "can I use
  this now" decisions.
- **`location_id.usage == 'internal'`** excludes customer/vendor/inventory-loss
  virtual locations that also carry quants in Odoo's accounting model — without
  this filter the summary includes nonsensical "locations."
- **Skip locations where free_qty <= 0** rather than showing "0 Units" rows —
  cleaner output, and a location fully reserved should not read as "available."
- **Branch on `detailed_type`** before querying: Consumable (`consu`) products
  are never quant-tracked in this codebase's product-type model (see the sibling
  KB entries on `detailed_type` filtering), so running the same query for them
  always returns empty and would misleadingly read as "never in stock" when
  they're actually always procurable. Give a distinct, honest message instead.

## Verification (rolled back)
Storable product with quants in 3 locations (100 qty/30 reserved → 70 free,
20 qty/0 reserved → 20 free, 15 qty/15 reserved → fully reserved): summary
correctly shows only the two free locations, sorted by quantity descending, and
excludes the fully-reserved one. Consumable → informative non-tracked message.
Storable with zero quants anywhere → "not available" message. No product
selected → blank.

## ⚠️ Pitfalls
- Don't use `product.qty_available` for a system-wide breakdown — it's a single
  aggregate number scoped by the current warehouse/company context, not a
  per-location breakdown.
- A non-stored compute running a `stock.quant.search()` per line recomputes on
  every relevant onchange in the form; fine for typical requisition line counts
  (tens), but flag as a scaling concern if reused somewhere with hundreds of
  editable lines per document.
