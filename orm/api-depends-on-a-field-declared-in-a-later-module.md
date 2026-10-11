# `@api.depends` on a Field Declared by a Later-Loading Module Aborts the Upgrade

| Field         | Value                     |
|---------------|---------------------------|
| Category      | orm                       |
| Odoo Versions | All                       |
| Severity      | 🔴 Critical               |
| Last Verified | 2026-09-12                |
| Author        | ENG/Gamal Mansour         |

**Tags:** `api.depends`, `compute`, `module-load-order`, `upgrade`, `registry`, `inheritance`

---

## Problem

Converting an `@api.onchange` to a stored compute looked like a like-for-like swap:

```python
# hr_payroll_customs -- BEFORE (worked)
@api.onchange('wage', 'l10n_sa_housing_allowance', 'food_allowance', ...)
def _onchange_salary(self): ...

# hr_payroll_customs -- AFTER (aborts the upgrade)
@api.depends('wage', 'l10n_sa_housing_allowance', 'food_allowance', ...)
def _compute_total_salary(self): ...
```

```
ValueError: Wrong @depends on '_compute_total_salary' (compute method of field
hr.contract.total_salary). Dependency field 'food_allowance' not found in model hr.contract.
```

`food_allowance` **is** a field on `hr.contract` — just declared in `custom_hr_employee`,
which loads *after* `hr_payroll_customs`.

## Root Cause

The two decorators resolve their field names at completely different moments:

| Decorator | When names are resolved |
|---|---|
| `@api.onchange` | lazily, at onchange time — every module is loaded by then |
| `@api.depends` | eagerly, while building the registry's trigger tree for **this** module |

So an onchange can reference a field contributed by any module in the database, while a
depends can only reference what exists in **its own module's dependency closure**. The same
trap applies to `related=` paths and to `_order` on a later-module field.

Adding the missing module to `depends` is usually not an option: the later module already
depends on this one, so it would be a cycle.

## Solution ✅

> Declare the field in the module that needs it in `@api.depends`, and drop the duplicate
> from the later module.

```python
# hr_payroll_customs/models/contract_inherit.py
class HRContractInherit(models.Model):
    _inherit = 'hr.contract'

    # Declared here rather than in custom_hr_employee: that module loads AFTER this one,
    # so @api.depends could not resolve the name at registry build.
    food_allowance = fields.Integer(string='Food Allowance', required=False)
```

Views in the later module can still reference it — a view may use any field on the model,
whichever module contributed it. Only `@api.depends`, `related=` and `_order` are bound by
load order.

### Catch it before the upgrade does

Field names in a depends are plain strings, so nothing flags this until the registry
builds. A static check over the suite is cheap: build each module's dependency closure from
the manifests, collect the fields each module declares per model, then flag any first hop
of an `@api.depends` that is **only** declared by a module further down the load order.

```python
later = any(first in declared[m2].get(model, set())
            for m2 in order[order.index(mod)+1:])
if first not in own | closure(mod).get(model, set()) and later:
    print(f"{mod}: {model}.{fn} depends on '{path}' declared only in a LATER module")
```

## ⚠️ Pitfalls

- **Reading the field at runtime proves nothing.** `rec.contract_id.food_allowance` works
  fine everywhere once the registry is up; only the *dependency declaration* is early.
- `ir_model_fields` in the database shows the field exists — it reflects the fully loaded
  registry, not the state at the failing module's own load step. Querying it to "verify"
  the field is available is misleading; check the manifest closure instead.
- The error surfaces on `-u`, in the middle of a multi-module upgrade, after some modules
  have already been processed. The remainder sit in state `to upgrade`.
- The reverse direction is safe: a **later** module may depend on an **earlier** module's
  field freely.
- A duplicate declaration in both modules also works, but leaves the winning definition's
  attributes decided by load order — prefer moving it.

## Verification

```bash
./odoo-bin -c <conf> -d <db> -u <module> --stop-after-init 2>&1 | grep -E "Wrong @depends|Modules loaded"
```

## References

- Related file: `orm/cron-writing-derived-values-back-onto-source-fields.md`
- Odoo source: `odoo/fields.py` (`resolve_depends`), `odoo/modules/registry.py` (`_field_triggers`)
