# Child Contract Models Missing `company_id` Break Cross-Model Computes & Preload Registries

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `multi-company`, `company_id`, `computed-fields`, `store`, `preload_registries`, `AttributeError`, `inheritance`, `record-rules`

---

## Problem

During Odoo server startup (`preload_registries`), the initialization sequence crashes with an `AttributeError` when a stored compute field tries to access `company_id` on a model where it was never defined:

```text
  File ".../odoo/modules/registry.py", line 129, in new
    odoo.modules.load_modules(registry, force_demo, status, update_module)
  ...
  File ".../odoo/addons/base/models/ir_model.py", line 2022, in _reflect_relation
    self.env.invalidate_all()
  File ".../odoo/api.py", line 857, in flush_all
    self._recompute_all()
  File ".../construction_subcontractor_portal/models/contract_subcontractor.py", line 146, in _compute_saudi_gtpl_governed
    company = rec.company_id or (rec.owner_contract_id.company_id if rec.owner_contract_id else self.env.company)
AttributeError: 'contract.subcontractor' object has no attribute 'company_id'
```

## Root Cause

1. Subordinate or detail models (e.g. `contract.subcontractor` linked to `contract.owner`) often omit `company_id`, relying implicitly on their parent.
2. Extension modules (such as portal, localization, or compliance add-ons) frequently expect `company_id` to exist following standard Odoo conventions and reference `rec.company_id` in stored `@api.depends` and compute functions.
3. During startup, `_reflect_relation` triggers `_recompute_all()` across all stored computed fields for records already in the database. When the ORM encounters `rec.company_id` on an unequipped model, it raises `AttributeError` and kills the server before port binding.

## Solution ✅

### 1. Equip the Base Model with a Synchronized `company_id`

Define `company_id` on the base model with compute, store, and fallback to `self.env.company`:

```python
# In base model (e.g., contract.subcontractor)
company_id = fields.Many2one(
    'res.company',
    string='Company',
    compute='_compute_company_id',
    store=True,
    readonly=False,
    default=lambda self: self.env.company,
    help="Operating company for this contract/record.",
)

@api.depends('owner_contract_id.company_id')
def _compute_company_id(self) -> None:
    for rec in self:
        if rec.owner_contract_id and rec.owner_contract_id.company_id:
            rec.company_id = rec.owner_contract_id.company_id
        elif not rec.company_id:
            rec.company_id = self.env.company
```

### 2. Implement Defensive Fallbacks in Extension Stored Computes

In extending modules, guard against missing fields dynamically using `hasattr` or safe relation navigation:

```python
# In extending module (e.g. construction_subcontractor_portal)
@api.depends('owner_contract_id', 'owner_contract_id.company_id', 'company_id', 'company_id.country_id')
def _compute_saudi_gtpl_governed(self) -> None:
    for rec in self:
        company = (hasattr(rec, 'company_id') and rec.company_id) or (
            rec.owner_contract_id.company_id if rec.owner_contract_id else self.env.company
        )
        country_code = company.country_id.code if company and company.country_id else False
        rec.is_saudi_gtpl_governed = bool(country_code == 'SA')
```

## ⚠️ Pitfalls

- **Multi-Company Security Holes:** Without `company_id` on business documents, multi-company record rules cannot filter them (`['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`). Every model representing a financial or contractual obligation MUST have `company_id`.
- **Preload Recomputation:** In databases with existing records, adding a stored compute or modifying `@api.depends` forces an immediate recomputation of all database rows during `load_modules`. Any missing field attribute crashes the startup immediately.

## References

- Related: `orm/stored-compute-related-field-attributeerror-preload.md`
- Related: `orm/per-company-config-not-ir-config-parameter.md`
