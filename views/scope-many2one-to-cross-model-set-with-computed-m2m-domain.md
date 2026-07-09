# Scoping a Many2one to a Cross-Model Set via a Computed Many2many + Fallback Domain

**Category:** Views
**Tags:** #views, #domain, #many2one, #many2many, #compute, #one2many, #ux
**Severity:** 🟢 Low
**Last Verified:** 2026-07-09
**Odoo Versions:** 17

## Problem
Need to restrict a `Many2one` field (here: `construction.material.requisition.line.
product_id`) to only the records that appear somewhere in a RELATED model reachable
through the parent (here: products used as `project.boq.item.product_id` for the
requisition's `project_id`). A plain domain string on the line can't express this —
`product.product` has no field to filter by project, so `domain="[('project_id','=',
parent.project_id)]"` style one-liners don't apply.

A hard restriction is also risky: if the target project's BOQ hasn't been broken
down to product-level yet (or the line has no project at all), a domain that
resolves to an empty ID list makes the `Many2one` **permanently unselectable** —
trapping the user with no way to add ANY product, including for legitimate,
unplanned procurement.

## Solution ✅
1. Add a non-stored computed `Many2many` field on the line holding the currently
   allowed ids, depending on the parent chain:

```python
boq_product_ids = fields.Many2many('product.product', compute='_compute_boq_product_ids',
    help="... falls back to unrestricted when empty ...")

@api.depends('requisition_id.project_id')
def _compute_boq_product_ids(self):
    for rec in self:
        project = rec.requisition_id.project_id
        if project:
            items = self.env['project.boq.item'].search([
                ('project_id', '=', project.id), ('product_id', '!=', False)])
            rec.boq_product_ids = items.product_id
        else:
            rec.boq_product_ids = False
```

`@api.depends('requisition_id.project_id')` on a one2many LINE (not the parent)
works correctly in the form's onchange spec — Odoo re-evaluates line-level computed
fields that depend on the parent when the parent field changes, even for NewId
lines being edited inline. (Mirrors an existing compute in the same file,
`_compute_analytic_distribution`, confirming the pattern is already proven in this
codebase.)

2. In the view, add the field invisible and set a **conditional** domain on the
   target `Many2one` that falls back to unrestricted when the computed set is
   empty — Odoo's domain mini-language supports Python-style ternaries and
   empty-collection falsiness (same rule that powers `invisible="not some_m2m"`):

```xml
<field name="boq_product_ids" column_invisible="1"/>
<field name="product_id" domain="[('id', 'in', boq_product_ids)] if boq_product_ids else []"/>
```

Do this via `position="attributes"` + `<attribute name="domain">` in an inheriting
view rather than editing the base field, if the restriction belongs to an add-on
module (project/BOQ awareness) layered on a base module that doesn't know about it.

## ⚠️ Pitfalls
- Don't compute the "no restriction" case by searching ALL records of the target
  model (e.g. `product.product.search([])`) just to populate the m2m — expensive
  and pointless. Leave it empty and let the ternary domain do the fallback.
- Verify with FOUR scenarios, not just the happy path: (a) project with BOQ
  products → restricted correctly, (b) no project on the line → unrestricted,
  (c) project set but its BOQ has zero product-linked breakdown lines →
  unrestricted (not a dead end), (d) a product genuinely outside the BOQ is
  excluded when restriction is active.
- `column_invisible="1"` (not `invisible="1"`) for a helper field injected into a
  `<tree>` via xpath, or it still reserves a column.

## Update — explicit mode toggle instead of a silent always-on filter (2026-07-09)
The user later asked for the restriction to be **opt-in per record**, not always
applied: a header `Selection` field (`request_type`: `internal` / `project`) where
`internal` shows every product unrestricted and `project` applies the BOQ filter.
This is a better UX than a silent automatic restriction — the user explicitly
declares intent instead of the system inferring it from whether a project happens
to be set.

- Gate the domain on the parent selection too:
  `domain="[('id','in',boq_product_ids)] if parent.request_type == 'project' and boq_product_ids else []"`.
  `parent.<field>` works for a HEADER selection field the same way it works for
  `parent.project_id` — no extra plumbing needed on the line.
- `required="expr"` is a VIEW-only conditional (XML attribute on the field tag).
  It is **not** a valid kwarg value for the Python `fields.Many2one(required=...)`
  constructor — that only accepts a static bool. Conditionally-required fields
  need BOTH: the view attribute (`required="request_type == 'project'"`) for UX,
  AND an `@api.constrains` raising `ValidationError` for the same condition, since
  the view-level required is bypassed entirely by API/import/script-created
  records that never render the form.
- Verify the constraint directly (not just the view attribute) — it is the actual
  enforcement; the view attribute is only a client-side convenience.
- After adding a view-level `domain="... if parent.<field> ..."` expression, sanity
  check it actually reaches the rendered arch via `record.get_view(view_id, 'form')`
  — a typo in the parent field name fails silently in the domain (evaluates to an
  eval error swallowed by the client, not a load-time XML error).
