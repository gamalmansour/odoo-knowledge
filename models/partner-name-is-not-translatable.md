# `res.partner.name` is not translatable — ship a second field, not a .po row

| Field         | Value |
|---------------|-------|
| Category      | models |
| Odoo Versions | 16, 17, 18 |
| Severity      | 🟡 Medium |
| Last Verified | 2026-08-16 |
| Author        | Gamal Mansour |

**Tags:** `res.partner`, `translation`, `i18n`, `bilingual`, `name_search`, `arabic`

---

## Problem

Shipping a data pack of 364 real hospitals with official names in two
languages. The obvious approach — an `i18n/ar.po` row per record:

```po
#. module: medical_data_sa
#: model:res.partner,name:medical_data_sa.hco_sa_moh_001
msgid "Prince Mohammad Bin Abdulaziz Hospital"
msgstr "مستشفى الأمير محمد بن عبدالعزيز"
```

The module installs. The language installs. No error anywhere. And the count
of translated records is **0 of 364**, while regions and specialties in the
very same `.po` translate perfectly.

## Root Cause

`res.partner.name` is declared without `translate=True`:

```python
# odoo/addons/base/models/res_partner.py
name = fields.Char(index=True, default_export_compatible=True)
```

This is a deliberate design choice, not an oversight — the name of a real
organisation is a proper noun, not a UI string. `city` is the same.

The importer reads the row, finds the target field is not translatable, and
drops it without complaint. Nothing distinguishes this from success, which is
why the neighbouring `medical.sa.region.name` (declared `translate=True`)
worked and made the failure look random.

## Solution ✅

Store the second name in its own indexed field and widen partner search to
include it:

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    sa_name_ar = fields.Char(
        string='Arabic Name',
        index='trigram',
        help='Official Arabic name as published by the Ministry of Health.',
    )

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if not value:
            return domain
        aggregator = (expression.AND
                      if operator in expression.NEGATIVE_TERM_OPERATORS
                      else expression.OR)
        return aggregator([domain, [('sa_name_ar', operator, value)]])
```

Extend `_search_display_name` rather than redeclaring `_rec_names_search`.
Base's list is `['complete_name', 'email', 'ref', 'vat', 'company_registry']`;
copying it into your module freezes it at today's contents and silently drops
whatever Odoo adds later — and it collides with any other module widening
partner search the same way. Extending the domain composes.

Add the field to the search view too, so one box matches either language:

```xml
<field name="name" string="Institution"
       filter_domain="['|', '|', ('name', 'ilike', self),
                       ('sa_name_ar', 'ilike', self),
                       ('city', 'ilike', self)]"/>
```

## ⚠️ Pitfalls

- **The failure is silent and partial.** Translatable fields in the same file
  work, so the natural conclusion is "my .po is fine, something else is wrong."
  Check `translate=True` on the target field before debugging the file.
- **This is the better design anyway, not a workaround.** A `.po` translation
  only shows in a matching UI language. A field shows in both at once — which
  is what you actually want, because a rep running an English interface still
  types the Arabic name into search.
- **`index='trigram'`** matters: `ilike '%…%'` on a plain index is a sequential
  scan, and this field exists to be searched.
- **Do not make `name` translatable via an override.** The blast radius is
  every partner in the database and every module that touches one.

## Verification

```python
# Arabic query, English interface
env['res.partner'].name_search('الملك فيصل', limit=3)
# -> [(id, 'King Faisal Specialist Hospital and Research Center - Jeddah'), ...]

# English still works
env['res.partner'].name_search('Dallah', limit=2)
```

## References

- `odoo/addons/base/models/res_partner.py` — field declaration
- `odoo/models.py` — `_search_display_name`, `_rec_names_search`
- Related: `misc/po-missing-module-comment-crashes-language-install.md`
