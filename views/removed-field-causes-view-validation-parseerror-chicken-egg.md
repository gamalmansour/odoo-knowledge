# Removed Field Causes View Validation ParseError (Chicken-and-Egg Manifest Deadlock)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All (16, 17, 18, 19)                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `ParseError`, `manifest`, `load-order`, `field-removal`, `ir.ui.view`, `validation`, `chicken-and-egg`

---

## Problem

When upgrading a module after removing a Python model field and cleaning up its corresponding XML views, Odoo fails during upgrade with a view validation `ParseError`:

```
odoo.tools.convert.ParseError: while parsing /path/to/module/views/another_view.xml:3
Field "xyz" does not exist in model "my.model"

View error context:
{'file': '/path/to/module/views/another_view.xml',
 'line': 3,
 'name': 'my.model.form.custom',
 'view': ir.ui.view(1341,),
 'view.model': 'my.model',
 'view.parent': ir.ui.view(126,),
 'xmlid': 'another_view_xmlid'}
```

Notice that the error points to `another_view.xml` (which doesn't even reference `xyz`), while the view that originally referenced `xyz` was edited in a different XML file later in the manifest `data` list!

## Root Cause

1. **Inherited View Validation on Every Change:** When Odoo parses an inherited view (e.g. in `another_view.xml`), it compiles and validates the entire inheritance tree for that base view (`base.view_partner_form`, etc.).
2. **Stale View in Database:** The view that previously contained `<field name="xyz"/>` still has the old arch stored in `ir_ui_view.arch_db` in PostgreSQL because its XML file hasn't been parsed yet.
3. **Manifest Load Order Deadlock (Chicken-and-Egg):** Because `another_view.xml` appears earlier in `__manifest__.py['data']` than the file containing the fix, Odoo validates the model against the existing DB views (which still contain `xyz`). Since the Python model definition no longer has `xyz`, view validation crashes and rolls back the transaction. The updated XML file later in the list is NEVER reached!

## Solution ✅

### 1. Fix the Stale View in the Database (Break the Deadlock)
Update `ir_ui_view` directly in PostgreSQL to remove the reference to the deleted field from `arch_db`:

```sql
-- For Odoo 17/18/19 where arch_db is jsonb:
UPDATE ir_ui_view 
SET arch_db = jsonb_set(arch_db, '{en_US}', to_jsonb(replace(arch_db->>'en_US', '<field name="xyz"/>', ''))) 
WHERE arch_db::text LIKE '%xyz%';
```

### 2. Correct Manifest `data` Ordering
Group views modifying the same parent models together in `__manifest__.py['data']`. Ensure views on primary models (like `res.partner` or `res.users`) are updated before downstream views or wizards that validate the same parent models.

### 3. Upgrade the Module
Run the upgrade cleanly:
```bash
python odoo-bin -c odoo.conf -u <module_name> --stop-after-init
```

## ⚠️ Pitfalls

- **Red Herring Error Location:** Do not assume `another_view.xml` is broken just because the traceback points to it. Check `SELECT id, name, model FROM ir_ui_view WHERE arch_db::text LIKE '%<missing_field>%';` to find the actual offending view in the DB.
- **Rollback Trap:** Editing only the XML file on disk will NOT fix the issue if an earlier XML file triggers validation first — the transaction rolls back before Odoo ever reads the updated file.

## Verification

Run module upgrade via CLI:
```bash
python odoo-bin -c odoo.conf -u <module_name> --stop-after-init
```
It should load all models, compile views cleanly, and exit with code 0.
