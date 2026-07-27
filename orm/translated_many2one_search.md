# Translated Name Searches and Database schema issues in `res.partner`

## Problem
In Odoo, standard text fields like `name` on core models like `res.partner` are used heavily in search logic across the entire ORM. Setting `translate=True` on an existing core `name` field via `_inherit` converts the underlying database column from `VARCHAR` to `JSONB` in newer Odoo versions. This will often cause the ORM to generate mismatched SQL queries where it tries to use the JSONB `->>` operator on a column that Postgres still perceives as `character varying`, leading to:
`psycopg2.errors.UndefinedFunction: operator does not exist: character varying ->> unknown`

Additionally, core mail functions like `_notify_get_recipients` use raw SQL to fetch `partner.name`. When `fetchall()` evaluates the column under the ORM's `translate=True` context, it can return a dictionary (e.g., `{'en_US': 'Name'}`) instead of a string, crashing email dispatches with:
`AttributeError: 'dict' object has no attribute 'encode'` inside `formataddr`.
## Solution ✅
Instead of making the core `name` field translated, create a new specific field for the alternative language (e.g., `arabic_name = fields.Char(string='Arabic Name')`). Then, to make this field searchable in all `Many2one` widgets globally without breaking core search queries, add the new field to the model's `_rec_names_search` list:

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    arabic_name = fields.Char(string='Arabic Name')
    _rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry', 'arabic_name']
```

> **This solves SEARCH, not DISPLAY.** `arabic_name` + `_rec_names_search` lets an
> English-UI user *find* a partner by its Arabic name — but every user still
> *sees* the one single `name`. It gives you nothing per-language on the display side.

## When you genuinely need per-language DISPLAY (translate=True is unavoidable)

If the real requirement is that **Arabic-UI users see the Arabic name and
English-UI users see the English name for the SAME partner** (mixed-language
teams entering names in both languages), then `arabic_name` is not enough — the
whole UI, reports and `display_name` render `name`, so you **must** keep
`translate=True` on `name`. In Odoo 19 this works, at a known **non-fatal** cost:

- **Load warnings you cannot remove** — these are Odoo *core* doing the same thing
  on top of your now-translated field, not a defect in your module:
  - `Translated stored related field (res.company.name) will not be computed correctly in all languages` — core's `res.company.name` is `related='partner_id.name', store=True` (`base/models/res_company.py`), so it inherits your translation.
  - `Index attribute on 'res.partner.name' ignored, only trigram index is supported for translated fields`.
  - Silencing them would mean editing core (forbidden) or a `post_load` logging filter — not worth it; they have **zero functional impact**.
- **Still add `arabic_name` + `_rec_names_search` alongside** — that is the search
  fix and it does not conflict with the translated `name`.
- **Keep watching the two crash modes below** (JSONB search SQL, email `formataddr`).
  ⚠️ **UPDATE 2026-07-28: the `formataddr` crash DOES reproduce on Odoo 19.**
  `mail.followers._get_recipient_data` fetches `res_partner.name` via raw SQL, so
  any notification that goes through it (e.g. the "you have been assigned"
  notify fired INSIDE `account.move` creation for `invoice_user_id`) receives a
  raw jsonb dict and dies with `AttributeError: 'dict' object has no attribute
  'encode'`. When that create was wrapped in a bare `except Exception` without a
  savepoint, the half-created invoice survived and posted as **"Paid" with no
  payment** — full post-mortem in
  [invoice-paid-on-post-zombie-from-swallowed-create-error](invoice-paid-on-post-zombie-from-swallowed-create-error.md).
  If email dispatch or assignment notifications break, this field is suspect #1.

**Decision rule:** need to *find* a partner by its Arabic name → `arabic_name`
only, leave `name` untranslated. Need the same partner to *display* differently
per user language → `translate=True` on `name`, and accept the harmless load
warnings as the price.

## ⚠️ Pitfalls
- In Odoo 16+, overriding `_get_name_search_domain` or `name_search` is discouraged because the ORM leverages `_search_display_name` via the `search` domain hook. Using `_rec_names_search` is the correct and officially supported method to add alternative searchable fields.
- Changing column types manually in Postgres or using `translate=True` on base fields breaks data integrity if not executed correctly via manual migration.
- The load warnings `Translated stored related field (res.company.name)…` and `Index attribute on 'res.partner.name' ignored…` are the **unavoidable, harmless** side effect of translating `name` (see the DISPLAY section) — they are core reacting to your translation, not a bug to chase into core files.
- Don't confuse the two needs: `arabic_name` (SEARCH) and `translate=True` (DISPLAY) are independent and are often both needed at once — the mistake is removing the translation to "fix the warnings" and silently breaking per-language display.

## Odoo Versions
Odoo 16, 17, 18, 19

_Last verified: 2026-07-28 (Odoo 19) — the `formataddr` crash mode is now CONFIRMED reproducible via `mail.followers._get_recipient_data` raw SQL (assignment notifications); see the zombie-invoice entry for the money-integrity blast radius._
