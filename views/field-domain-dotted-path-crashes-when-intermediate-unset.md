# Field-Level Many2one Domain With a Dotted Path Crashes the Client When the Intermediate Is Unset

**Category:** Views
**Tags:** #views, #domain, #many2one, #uom, #client-crash, #evalerror, #gotcha
**Severity:** 🔴 Critical
**Last Verified:** 2026-07-11
**Odoo Versions:** 16, 17, 18, 19

## Problem
A `Many2one` field carries a **field-level** (Python `fields.Many2one(domain=...)`) domain
that traverses a dotted path through ANOTHER relational field:

```python
uom_id = fields.Many2one('uom.uom',
    domain="[('category_id', '=', product_id.uom_id.category_id)]")   # ❌
```

The web client evaluates this domain **in the browser** every time the dropdown opens. When
the intermediate field is empty (`product_id` not picked yet), `product_id.uom_id` is
`undefined`, and reading `.category_id` off it throws:

```
UncaughtPromiseError > EvalError
Can not evaluate python expression: ([('category_id', '=', product_id.uom_id.category_id)])
Error: Cannot read properties of undefined (reading 'category_id')
    at evaluateExpr ... at getFieldDomain ... at Many2OneField.getDomain
```

The record can't be edited — the moment the user clicks the UoM field before setting a
product, the form errors. (Same failure mode whether the domain is on the field definition
or repeated as a `<field domain="...">` in the view.)

## Solution ✅
Use the Odoo-core pattern: a **related helper field** for the last hop, and a domain that
references only that single (top-level) field — never a dotted path:

```python
product_uom_category_id = fields.Many2one('uom.category',
    related='product_id.uom_id.category_id', string='UoM Category')
uom_id = fields.Many2one('uom.uom',
    domain="[('category_id', '=', product_uom_category_id)]")         # ✅
```

When `product_id` is empty the related field is simply `False`, so the domain becomes
`[('category_id', '=', False)]` — an empty result set, **not a crash**. When a product is
set it filters to compatible units, exactly as intended. This is precisely how core
`stock.move` / `sale.order.line` scope their `product_uom`.

**Add the helper field to every view that renders the target field**, invisible, so the
client has the value to evaluate the domain:
```xml
<field name="product_uom_category_id" column_invisible="1"/>   <!-- in a tree -->
<field name="product_uom_category_id" invisible="1"/>          <!-- in a form -->
```
Miss this and the client evaluates the domain against an `undefined` helper field — the
same crash, one level up. `column_invisible` for a `<tree>`, `invisible` for a `<form>`.

## ⚠️ Pitfalls
- **The rule:** a client-evaluated domain (field-level OR view `<field domain>`) may only
  reference **top-level fields of the current record** — never `a.b.c` dotted paths. Any hop
  through a relation must be pre-resolved into a related field on the record.
- **Field-level domains render everywhere the field appears** — one bad field definition
  crashes every tree/form that shows it (here: the Work Order Materials tab AND the Store
  Issue line tree). Fixing the field definition fixes all of them at once; conversely, a
  view-level `<field domain>` override only fixes that one view (and *replaces* the field
  domain — see [scope-many2one-to-cross-model-set-with-computed-m2m-domain]).
- **Grep the codebase for the anti-pattern:** `grep -rn "\.uom_id\.\|_id\..*\._id\." --include=*.py`
  style — dotted paths of length ≥2 inside a `domain="..."` string are the smell.
- **No migration / data impact** — it's a UI-domain fix; stored values are untouched.
- **Verify via the arch, not just the model:** `Model.get_view(view_id,'form')['arch']` must
  show the OLD dotted path gone and the helper field present, in each affected view.

## Related
- `views/scope-many2one-to-cross-model-set-with-computed-m2m-domain.md` — computed-set
  domains + the "view domain replaces field domain" rule.
- Existing correct usage in this repo: `construction_waste.waste` already resolves
  `product_uom_category_id` this way.
