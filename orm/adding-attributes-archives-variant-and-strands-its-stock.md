# Adding attributes to a stocked product archives the original variant WITH its stock

**Category:** ORM / Inventory
**Date:** 2026-07-22
**Project:** activity (store, client Batch-2 "free_qty always 0")

## Symptom
Client: "products have size/color variants and free_qty is always 0 even though there IS quantity." API and backend both show 0 on every visible variant.

## Root cause (reproduced deterministically)
Order of operations trap:
1. Create storable product → it has one implicit variant.
2. Set quantity on hand (quant lands on that variant).
3. THEN add attribute lines (size/color) → Odoo **archives** the original variant and generates fresh active variants.
4. The quant stays on the **archived** variant. Every active variant reads 0; any serializer that filters `product_variant_ids.filtered('active')` sums to 0. Nothing errors anywhere.

```python
tmpl = create(storable); quant(tmpl.product_variant_ids, 10)
tmpl.write({'attribute_line_ids': [...]})   # old variant: active=False, free_qty=10
tmpl.product_variant_ids.filtered('active').mapped('free_qty')  # [0.0, 0.0]
```

## Fix / guidance
- **Data-side fix (client instruction):** re-enter quantities per variant AFTER the attributes exist (inventory adjustment per variant). Rule: *variants first, stock second*.
- Diagnose fast with: `tmpl.with_context(active_test=False).product_variant_ids.mapped(lambda v: (v.active, v.free_qty))` — stranded stock shows as `(False, qty)`.
- Don't "fix" this in API code by summing archived variants — the stranded quant is a data error (that stock is unsellable/unreservable for the real variants).

## Rule of thumb
When a stock number "exists but reads 0", check archived variants before suspecting the compute: `active_test=False` reveals where the quants actually sit.
