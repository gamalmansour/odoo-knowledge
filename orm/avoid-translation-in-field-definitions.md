# Do NOT Use `_()` Inside Field Definitions (Class Body)

| Field         | Value                          |
|---------------|--------------------------------|
| Category      | orm                            |
| Odoo Versions | All (14, 15, 16, 17, 18, 19)  |
| Severity      | 🔴 Critical                    |
| Last Verified | 2026-08-24                     |
| Author        | ENG/Gamal Mansour              |

**Tags:** `translation`, `i18n`, `fields`, `_()`, `class-body`, `bug`

---

## Problem

Using `_()` inside field `string=` or `help=` parameters causes translations to be evaluated **at module import time**, not at request time. This means the string is always in the server's default language, ignoring the user's language completely.

```python
# ❌ WRONG — evaluated once at import, always returns server language
class CustomerLevel(models.Model):
    name = fields.Char(string=_('Level Name'))        # BUG
    color = fields.Integer(string=_('Color Index'))   # BUG

    # Odoo 19: _sql_constraints is ignored entirely — see the note below
    _unique_name = models.Constraint('UNIQUE(name)', _('Name must be unique!'))  # BUG
```

No error is raised — it silently fails to translate for users with different languages.

## Root Cause

In Python, class bodies are executed once when the module is first imported. `_()` at that point resolves against the server's locale at startup, not the user's `lang` context at request time. Odoo's i18n system works differently for field labels: it reads `string=` as a raw English string and translates it on-the-fly using `.po` files.

## Solution ✅

Remove `_()` from `string=`, `help=`, and constraint messages entirely. Use plain English strings — Odoo's i18n handles the translation automatically via `.po` files:

```python
# ✅ CORRECT
class CustomerLevel(models.Model):
    name = fields.Char(string='Level Name')        # translated via i18n
    color = fields.Integer(string='Color Index')   # translated via i18n

    _unique_name = models.Constraint('UNIQUE(name)', 'Name must be unique!')  # plain string
```

Keep `_()` only inside **method bodies** where it runs at request time:

```python
# ✅ Correct use of _() — inside a method
def action_confirm(self):
    raise UserError(_('Cannot confirm without lines.'))
```

## ⚠️ Pitfalls

- This bug is **silent** — no error, no warning. The string just never translates.
- It also affects constraint error messages and `Selection` labels if wrapped.
- Affects: `string=`, `help=`, `selection` list items in field defs, and constraint messages.
- **Odoo 19:** `_sql_constraints` is no longer supported at all — it logs `Model attribute '_sql_constraints' is no longer supported` and the constraint is never created. Use `models.Constraint(...)` / `models.UniqueIndex(...)` class attributes, and keep their messages as plain English strings for the same reason. See `Best Practices/odoo-19-warnings.md`.
- **Do NOT** wrap `compute=`, `inverse=`, `search=` — those are method names, not strings.

## Verification

After removing `_()` from field definitions, switch the UI language to Arabic (or any non-English language) and verify that field labels translate correctly from the `.po` file.

## References

- [Odoo ORM Fields Documentation](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#fields)
- Fixed in: `custom/customer_level_chart/models/customer_level.py`
- Fixed in: `custom/customer_level_chart/models/res_partner.py`
- Fixed in: `custom/stock_valuation_report/models/stock_move_valuation.py`
- Fixed in: `custom/delivery_vehicle/models/delivery_vehicle.py`
- Fixed in: `custom/product_secondary_uom/models/product_template.py`
- Fixed in: `custom/product_secondary_uom/models/stock_quant.py`
- Fixed in: `custom/product_secondary_uom/models/stock_move.py`
- Fixed in: `custom/product_secondary_uom/models/stock_picking_batch.py`

> **Note (2026-06-06):** Confirmed this WARNING appears in Odoo 19 (SH) even when using `_()` inside class body at field `string=` or `help=`. The warning stack trace clearly shows `_get_translation_source` failing because no lang context exists at import time. The fix is identical — plain English strings in field defs.
