# Translated Name Searches and Database schema issues in `res.partner`

## Problem
In Odoo, standard text fields like `name` on core models like `res.partner` are used heavily in search logic across the entire ORM. Setting `translate=True` on an existing core `name` field via `_inherit` converts the underlying database column from `VARCHAR` to `JSONB` in newer Odoo versions. This will often cause the ORM to generate mismatched SQL queries where it tries to use the JSONB `->>` operator on a column that Postgres still perceives as `character varying`, leading to:
`psycopg2.errors.UndefinedFunction: operator does not exist: character varying ->> unknown`

## Solution ✅
Instead of making the core `name` field translated, create a new specific field for the alternative language (e.g., `arabic_name = fields.Char(string='Arabic Name')`). Then, to make this field searchable in all `Many2one` widgets globally without breaking core search queries, add the new field to the model's `_rec_names_search` list:

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    arabic_name = fields.Char(string='Arabic Name')
    _rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry', 'arabic_name']
```

## ⚠️ Pitfalls
- In Odoo 16+, overriding `_get_name_search_domain` or `name_search` is discouraged because the ORM leverages `_search_display_name` via the `search` domain hook. Using `_rec_names_search` is the correct and officially supported method to add alternative searchable fields.
- Changing column types manually in Postgres or using `translate=True` on base fields breaks data integrity if not executed correctly via manual migration.

## Odoo Versions
Odoo 16, 17, 18, 19
