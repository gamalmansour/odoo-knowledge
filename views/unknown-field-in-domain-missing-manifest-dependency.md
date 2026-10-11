# Unknown field "_unknown.field" in domain of python field (Missing Manifest Dependency)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `domain`, `_unknown`, `depends`, `manifest`, `ParseError`, `view-validation`

---

## Problem

When installing a module that defines a `Many2one` field with a Python domain filtering on the target comodel's fields, view parsing crashes with a `ParseError`:

```
odoo.tools.convert.ParseError: while parsing .../views/my_view.xml:30
Error while validating view near:
    <field name="my_field_id"/>

Unknown field "_unknown.some_field" in domain of python field 'my_field_id' ([('some_field', 'in', ['val1', 'val2'])]))
```

## Root Cause

In Odoo, when a model contains a `fields.Many2one('target.model')` with a domain like `domain="[('category', 'in', ['mixer', 'other'])]"`, and `target.model` is defined in another module (e.g. `construction_equipment`), but that module is **not declared in `'depends'`** in `__manifest__.py`:
1. If the target module is not yet installed or loaded, Odoo creates a dummy placeholder model named `_unknown`.
2. During module installation, Odoo's view validator inspects fields in the XML view and evaluates the domain attached to the Python field definition.
3. Because the comodel is `_unknown`, resolving the domain field path (`category`) on `_unknown` fails with `Unknown field "_unknown.category"`.

## Solution ✅

Add the module that defines the target comodel to the `'depends'` list in `__manifest__.py`:

```python
# __manifest__.py
{
    'name': 'My Module',
    'depends': [
        'base',
        'construction_project',
        'construction_equipment',  # <- Must explicitly declare the module defining the comodel
    ],
}
```

## ⚠️ Pitfalls

- Even if the view itself does not declare `domain="..."` inline in XML, Odoo's view validator checks the **Python field definition's domain** whenever that field appears in a form/tree/search view (`<field name="pump_equipment_id"/>`).
- Always ensure that every model referenced in `fields.Many2one('comodel.name')` has its owning module declared in `'depends'`.

## Verification

Re-run module installation via CLI or Web UI:
```bash
odoo-bin -c odoo.conf -d db_name -i my_module --stop-after-init
```
Verify that the target module is pulled automatically and installed first, and the view loads cleanly with code 0.
