# Manifest XML File Load Order Issues (External ID not found)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-05-30                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `manifest`, `xml`, `load order`, `parent menu`, `external id`

---

## Problem

When installing or upgrading an Odoo module, a `ValueError: External ID not found in the system` or a `ParseError` occurs. This happens in two scenarios:
1. An XML element (e.g., a menuitem, action, or view) refers to an external ID defined in another XML file *within the same module* that hasn't been parsed yet.
2. An XML element refers to an external ID defined in *another module* which is either missing from the `'depends'` list in `__manifest__.py`, or the referenced ID has an incorrect namespace prefix (e.g. referencing `module_a.action_id` when the action is actually defined in `module_b`).

```
ValueError: External ID not found in the system: module_name.parent_menu_id
```

## Root Cause

1. **Load Order**: Odoo loads XML files in the exact sequence they are declared in the `data` list in `__manifest__.py`. If a file (e.g., `dashboard_views.xml`) defines a menuitem with `parent="menu_root"` before the file defining `menu_root` (e.g., `menu_views.xml`) is loaded, Odoo's registry won't find the parent's external ID, causing installation to fail.
2. **Missing Dependencies or Incorrect Namespaces**: If a module references an XML ID from another module (e.g., `job_costing_dashboard.action_material_cost_sheet_line`), Odoo will fail to find it if the defining module is not loaded first (missing from `'depends'` in `__manifest__.py`) or if the ID is incorrectly prefixed.
3. **Omitted Files**: The XML file containing the definition simply wasn't added to the `data` list in `__manifest__.py` at all. This is extremely common when creating new views or actions and forgetting to register the file.

## Solution ✅

1. **Order Manifest Data Files by Dependency**: Ensure that files defining parent menus, actions, or base categories are loaded **before** child menus, custom action views, or wizard elements.
2. **Explicitly Declare Module Dependencies**: Any module whose XML ID is referenced must be listed in the `'depends'` key of the `__manifest__.py` file.
3. **Verify XML ID Namespaces**: Ensure the prefix of the external ID matches the exact module where the record is originally defined (e.g. check actions in `job_costing_dashboard` instead of assuming they belong to `odoo_job_costing_management`).
4. **Register the Missing XML File**: Double-check the `data` list in `__manifest__.py` to ensure the file containing the external ID is actually listed.

Example of correct ordering and dependency structure:
```python
# __manifest__.py
{
    'name': 'My Module',
    'depends': [
        'project',
        'job_costing_dashboard',  # Required for external actions referenced in menus
    ],
    'data': [
        'views/menu_views.xml',        # Loads root menus & core parent menus first
        'views/dashboard_views.xml',   # Loads dashboard menu, which references parent menu
    ],
}
```

## ⚠️ Pitfalls

- **Circular Dependencies**: Do not create menus/views in two different modules that reference each other.
- **Assumed Namespaces**: Do not assume an action or view belongs to a core module just because it is related to it. Always search the codebase for the `<record id="..."` declaration to find the actual defining module.

## Verification

To verify, reinstall the module or run Odoo with:
```bash
odoo-bin -c <config> -u <module_name> -d <database>
```
The module should load successfully without any registry lookup errors.
