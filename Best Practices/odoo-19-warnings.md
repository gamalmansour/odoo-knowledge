# Odoo 19 Common Installation Warnings

## 1. `_sql_constraints` Deprecation
**Warning:** `Model attribute '_sql_constraints' is no longer supported, please define model.Constraint on the model.`

### ⚠️ Pitfall
In Odoo 19, the legacy `_sql_constraints = [...]` list attribute has been completely deprecated and will throw a warning on module load.

### Solution ✅
Define the constraint directly on the class as an attribute using `models.Constraint`:

**Old (Odoo 18-):**
```python
_sql_constraints = [
    ('name_company_uniq', 'unique (name, company_id)', 'The company name must be unique per company!')
]
```

**New (Odoo 19+):**
```python
_name_company_uniq = models.Constraint(
    'unique (name, company_id)', 
    'The company name must be unique per company!'
)
```

## 2. Translation `_()` inside Constraints
**Warning:** `no translation language detected, skipping translation`

### ⚠️ Pitfall
Never wrap constraint string messages with `_()` inside the Model class definition. Constraints are evaluated when the module is imported, before the environment or language context exists.

### Solution ✅
Remove `_()` from constraint string definitions. Odoo extracts these automatically for `.pot` files without needing the wrapper.

## 3. `tracking=True` on Non-Tracking Models
**Warning:** `Field [...]: unknown parameter 'tracking', if this is an actual parameter you may want to override the method _valid_field_parameter...`

### ⚠️ Pitfall
You added `tracking=True` to a field, but the model does not inherit from `mail.thread`. In Odoo 19, this produces an explicit warning instead of silently ignoring it.

### Solution ✅
Either inherit `['mail.thread']` in the model, or remove `tracking=True` from the field definition.

## 4. Duplicate Field Labels
**Warning:** `Two fields ([...]) of [...] have the same label...`

### ⚠️ Pitfall
Multiple fields on the same model share the exact same `string='...'` attribute, which causes confusion in the UI (e.g., Studio, Import/Export).

### Solution ✅
Ensure `string` attributes are unique per model. For example, change `string='Driver'` to `string='Driver Name'` for character fields.
