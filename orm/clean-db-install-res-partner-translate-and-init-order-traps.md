# Clean-DB Install Crashes: `res.partner.name` `translate=True` Out-of-Sync with `res.company.name` & `init()` Table Order Trap

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `clean-db`, `install`, `translate`, `jsonb`, `res.partner`, `res.company`, `init`, `table_exists`, `UndefinedFunction`, `UndefinedTable`

---

## Problem

When installing a custom module suite onto a **clean database** (`-i ...`), two schema-initialization ordering bugs crash the registry load even though the same code appeared to work on an already-installed database during `-u`:

### 1) `res.partner.init()` queries a custom model table before `_auto_init()` creates it
```
psycopg2.errors.UndefinedTable: relation "sale_visit" does not exist
LINE 8: OR id IN (SELECT partner_id FROM sale_visit WHERE partner_id IS NOT NULL)
```

### 2) Setting `name = fields.Char(translate=True)` on `res.partner` crashes `res.company` queries during XML loading
```
WARNING pure_test odoo.fields: Translated stored related field (res.company.name) will not be computed correctly in all languages
...
ERROR pure_test odoo.sql_db: bad query: SELECT "res_company"."id" FROM "res_company" ... ORDER BY "res_company"."sequence", "res_company"."name"->>'en_US'
psycopg2.errors.UndefinedFunction: operator does not exist: character varying ->> unknown
```

## Root Cause

1. **Model Registration Order in `registry.init_models()` (`odoo/orm/registry.py`):**
   `init_models()` iterates over `model_names` in the order models were first registered in the Registry, calling `model._auto_init()` followed immediately by `model.init()` for each model one by one. Because `res.partner` is registered in `base` (module #1) while a custom model like `sale.visit` is registered in `sale_visit`, `res.partner.init()` executes **before** `sale.visit._auto_init()` has created the `sale_visit` table on a clean database.

2. **Stored Related Field `res.company.name` (`related='partner_id.name', store=True`) Not Converted to `jsonb`:**
   In core `base`, `res.company.name` is a stored related field pointing to `partner_id.name`. When a custom module (`customer_level_chart`) inherits `res.partner` and redefines `name = fields.Char(translate=True)`, `setup_models()` propagates `translate=True` to `res.company.name` in Python memory. However, `load_module_graph()` only passes the models explicitly declared/inherited in `customer_level_chart` to `registry.init_models()`. Because `customer_level_chart` did not inherit `res.company`, `res.company._auto_init()` is never called during that module's table creation phase — leaving `res_company.name` as `character varying` (`varchar`) in PostgreSQL while the ORM immediately emits `ORDER BY "res_company"."name"->>'en_US'` when evaluating `self.env.companies` during XML `ir.rule` loading.

## Solution ✅

### Fix 1: Guard custom table references inside inherited base-model `init()` with `table_exists`

```python
from odoo.tools.sql import table_exists

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def init(self) -> None:
        super().init()
        visit_clause = (
            "OR id IN (SELECT partner_id FROM sale_visit WHERE partner_id IS NOT NULL)"
            if table_exists(self.env.cr, 'sale_visit')
            else ""
        )
        self.env.cr.execute(f"""
            UPDATE res_partner
               SET valid_customer = TRUE
             WHERE is_company = TRUE
               AND (
                   customer_rank > 0
                   OR id IN (SELECT partner_id FROM sale_order WHERE partner_id IS NOT NULL)
                   {visit_clause}
               )
               AND valid_customer IS NOT TRUE;
        """)
```

### Fix 2: Explicitly inherit `res.company` in the module that sets `translate=True` on `res.partner.name`

```python
class ResPartnerLevel(models.Model):
    _inherit = 'res.partner'

    name = fields.Char(translate=True)


class ResCompanyLevel(models.Model):
    """Ensure res.company._auto_init() runs during module install so
    res_company.name (stored related to partner_id.name) is converted to
    jsonb at the same time as res_partner.name, before XML record rules
    query res.company."""
    _inherit = 'res.company'
```

## ⚠️ Pitfalls

- Relying on `-u` on an existing database masks both bugs: on an existing database, `sale_visit` already exists before `ResPartner.init()` is added, and `res_company.name` may have been converted by a later module that happened to inherit `res.company`.
- Whenever changing `translate=True` on a field that has `store=True` `related=` dependents on other models, check Odoo's startup log for `WARNING ... odoo.fields: Translated stored related field (<model>.<field>)` and include `_inherit = '<model>'` in the same module so `_auto_init()` converts both columns together.

## Verification

```bash
# Clean DB install of all custom modules must exit 0 with no UndefinedTable or UndefinedFunction:
./odoo-bin -c custom.conf -d pure_test --no-http --stop-after-init -i sale_visit,customer_level_chart
psql -h localhost -p 5433 -U odoo -d pure_test -c "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name IN ('res_partner', 'res_company') AND column_name = 'name';"
# Expected: both res_partner.name and res_company.name have data_type = jsonb
```

## References

- Related file: `setup/clean-db-install-verification-demo-as-data-and-missing-rule-fields.md`
