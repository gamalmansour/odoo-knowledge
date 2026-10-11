# Stored Compute `@api.depends` Traversing Non-Existent Related Field Aborts Preload Registries

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `api.depends`, `preload_registries`, `AttributeError`, `inheritance`, `cross-model`

---

## Problem

> During Odoo server startup or module upgrade, the process aborts during `preload_registries` / `_reflect_relation` with an `AttributeError` inside a stored compute method:

```text
  File ".../odoo/modules/loading.py", line 206, in load_module_graph
    registry.init_models(env.cr, model_names, {'module': package.name}, new_install)
  File ".../odoo/modules/registry.py", line 618, in init_models
    func()
  File ".../odoo/addons/base/models/ir_model.py", line 2022, in _reflect_relation
    self.env.invalidate_all()
  File ".../odoo/api.py", line 839, in invalidate_all
    self.flush_all()
  File ".../odoo/api.py", line 857, in flush_all
    self._recompute_all()
  File ".../odoo/api.py", line 850, in _recompute_all
    self[field.model_name]._recompute_field(field)
  File ".../odoo/models.py", line 7360, in _recompute_field
    field.recompute(records)
  File ".../odoo/fields.py", line 1493, in compute_value
    records._compute_field_value(self)
  File ".../odoo/models.py", line 5297, in _compute_field_value
    fields.determine(field.compute, self)
  File ".../construction_subcontractor_portal/models/contract_subcontractor.py", line 154, in _compute_subcontract_ratios
    main_val = main_contract.contract_value if main_contract else 0.0
AttributeError: 'contract.owner' object has no attribute 'contract_value'
```

## Root Cause

> 1. A stored computed field defines an `@api.depends` that traverses a Many2one relation (e.g., `@api.depends('contract_value', 'owner_contract_id.contract_value')`), but the related model (`contract.owner`) does **not** have a field with that exact name (in `contract.owner` the fields are `contract_value_current` and `contract_value_original`).
> 2. When Odoo reflects relations during model initialization, it triggers `self.env.invalidate_all()` which calls `self._recompute_all()` for pending stored computed fields.
> 3. Unlike Python syntax errors, this error only manifests when there are existing database records and Odoo executes the compute method (`main_contract.contract_value`), crashing the server before any web worker or HTTP request can be served.

## Solution ✅

> 1. Check the target model to confirm its actual field names (`contract_value_current`, `contract_value_original`).
> 2. Update `@api.depends` to depend on the real stored fields on the related model.
> 3. Update the method logic with defensive fallbacks:

```python
# Before (crashes on preload_registries)
@api.depends('contract_value', 'owner_contract_id.contract_value')
def _compute_subcontract_ratios(self) -> None:
    for rec in self:
        main_contract = rec.owner_contract_id
        main_val = main_contract.contract_value if main_contract else 0.0
        ...

# After (safe, robust)
@api.depends('contract_value', 'owner_contract_id.contract_value_current', 'owner_contract_id.contract_value_original')
def _compute_subcontract_ratios(self) -> None:
    for rec in self:
        main_contract = rec.owner_contract_id
        main_val = (main_contract.contract_value_current or main_contract.contract_value_original or 0.0) if main_contract else 0.0
        ...
```

> 4. As a defensive practice across related models, declare a convenience alias on the parent model (e.g. `contract.owner`):
```python
contract_value = fields.Monetary(
    string='Contract Value',
    related='contract_value_current',
    store=False,
    help="Convenience alias for contract_value_current across contract models."
)
```

## ⚠️ Pitfalls

- **Do NOT depend on non-stored fields in `@api.depends` for stored compute fields:** If `subcontract_ratio_pct` has `store=True`, any traversed path in `@api.depends` must resolve to stored fields. Depending on `owner_contract_id.contract_value` if it is `store=False` would defeat trigger cache invalidation. Always depend directly on the underlying stored fields (`owner_contract_id.contract_value_current`, `owner_contract_id.contract_value_original`).

## References

- Related: `orm/related-field-keyerror-reference.md`
- Related: `orm/api-depends-on-a-field-declared-in-a-later-module.md`
