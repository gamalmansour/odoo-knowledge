# A Modifier on a One2many `<list>` Does Not Exist on Mobile — and Was Never Security

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-01                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `one2many`, `readonly`, `studio`, `mobile`, `security`, `sale.order.line`, `price_unit`

---

## Problem

> A field inside a one2many is locked with `readonly="<condition>"` — often set
> in Studio, which writes the xpath against the `<list>` it can see. It works
> perfectly on the desktop for months. Then somebody opens the same record on a
> phone, or in the Odoo mobile app, and edits the field freely.
>
> The usual conclusion — "the mobile app has a bug" — is wrong twice over. The
> rule was never on the surface a phone uses, and a view modifier was never
> going to hold anyway.

## Root Cause

**A one2many is rendered by up to three different sub-views in the SAME form**,
and a modifier written against one of them does not exist in the others.
`sale.order.form` is the canonical example (`addons/sale/views/sale_order_views.xml`,
Odoo 19):

| Sub-view | Line | Used by | Editable? |
|---|---|---|---|
| `<list>` | 600 | desktop | yes — inline |
| `<form>` | 506 | the dialog opened when a line is tapped — **the mobile edit surface** | yes |
| `<kanban class="o_kanban_mobile">` | 759 | narrow screens / the mobile app | display only |

A Studio rule patches only the `<list>`:

```xml
<xpath expr="/form/sheet/notebook/page[@name='order_lines']/field[@name='order_line']/list//field[@name='price_unit']"
       position="attributes">
    <attribute name="readonly">salesman_id in [82, 12, 74, …] and product_id not in [4207, 4410]</attribute>
</xpath>
```

On a phone the client renders the kanban and edits through the dialog form.
Neither carries the attribute, so the field is open.

Two further defects travel with this shape:

- **Hardcoded ids.** Studio conditions are written as literal id lists. Anybody
  added later is silently exempt (8 of the live salespeople were), and ids of
  archived users linger forever.
- **A view modifier is a hint to the browser.** An API key, an Excel import or a
  hand-made RPC writes the field whatever any view says.

## Solution ✅

**Enforce in `create`/`write` on the model; keep the view modifier as courtesy.**

```python
PRICE_GROUP = 'my_module.group_sale_price_editor'

def _price_is_locked(self):
    # env.su honoured on purpose: code running as superuser already decided.
    return not (self.env.su or self.env.user.has_group(PRICE_GROUP))

def write(self, vals):
    if 'price_unit' in vals and self._price_is_locked():
        blocked = self.filtered(lambda l: l._price_is_controlled())
        if blocked:
            raise AccessError(_("You may not change the unit price of %s.",
                                ", ".join(blocked.mapped('product_id.display_name'))))
    return super().write(vals)
```

**Normalise on create, refuse on write.** A `write` naming the field is always a
deliberate edit. A `create` carrying it came from an integration or an import —
the web client does **not** send a readonly field at all — and those callers
usually just echo back the price they were handed. Raising there breaks a
nightly job over a value nobody meant to change:

```python
@api.model_create_multi
def create(self, vals_list):
    lines = super().create(vals_list)
    if self._price_is_locked():
        for line, vals in zip(lines, vals_list):
            if 'price_unit' not in vals or not line._price_is_controlled():
                continue
            submitted = line.price_unit
            line._reset_price_unit()          # core's own recompute seam
            if line.currency_id.compare_amounts(submitted, line.price_unit):
                line.order_id.message_post(body=_("… submitted as %s, reset to %s …",
                                                  submitted, line.price_unit))
    return lines
```

Then patch **every editable** sub-view, driven by a non-stored boolean so the
condition is a group, not an id list:

```xml
<xpath expr="//field[@name='order_line']/list//field[@name='price_unit']" position="before">
    <field name="can_edit_price" column_invisible="1"/>
</xpath>
<xpath expr="//field[@name='order_line']/list//field[@name='price_unit']" position="attributes">
    <attribute name="readonly">not can_edit_price</attribute>
</xpath>
<!-- and the same pair against .../form//field[@name='price_unit'] -->
```

## ⚠️ Pitfalls

- **Count the sub-views before writing the xpath.** One line of lxml settles it
  and costs nothing:
  ```python
  arch.xpath("//field[@name='order_line']/list//field[@name='price_unit']")   # → 1
  arch.xpath("//field[@name='order_line']/form//field[@name='price_unit']")   # → 1
  arch.xpath("//field[@name='order_line']/kanban//field[@name='price_unit']") # → 1
  ```
- **Mirror core's OWN exemptions, do not invent your own.** On `sale.order.line`,
  `_compute_price_unit` skips `is_downpayment` and `_is_global_discount()`
  because those prices cannot come from a product. Guard them and you break the
  down payment wizard and the order discount wizard for every ordinary user.
- **`technical_price_unit` cannot detect a create-time override.** It mirrors the
  computed price and core compares the two to spot a manual edit — but
  `_add_precomputed_values` copies `price_unit` into it on create, so after a
  create they are always equal. Compare against a recompute, not against it.
- **The compute path does not call `write()`.** `_reset_price_unit` uses
  `record.update()`, i.e. cache then `_write`, so a public `write` override does
  not recurse and does not fight the pricelist. Verify this before overriding
  `write` on any computed-but-editable field (`store=True, readonly=False`).
- **Tests must use `with_user`.** `TransactionCase` runs as superuser and the
  guard honours `env.su`, so the obvious test goes green while the check never
  runs — see `backend/env-su-guard-silently-passes-in-transactioncase.md`.
- **Delete the old Studio xpath.** Two views setting the same attribute on the
  same field conflict and the last applied wins, so a user who holds the new
  group but appears in the old hardcoded list stays locked for no visible reason.
- Related: [prevent-manual-editing-one2many-modal.md](prevent-manual-editing-one2many-modal.md)
  — the same gap reached from `edit="false"` on the list.

## Verification

1. Desktop, user without the group → the cell is greyed out.
2. **Narrow the window or use the mobile app, tap a line** → the dialog field is
   greyed out. This is the case that was open.
3. Grant the group, reload → editable in both.
4. Revoke it, then write the field over the API and create a line over the API →
   the write raises, the create is reset and recorded.
