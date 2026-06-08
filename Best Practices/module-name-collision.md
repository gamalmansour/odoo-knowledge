# 📝 Module Name Collision in addons_path

**Category**: Best Practices
**Tags**: #addons #collision #missing_column #view_error
**Odoo Versions**: All

## ❌ Problem / Symptom
If you have two custom modules with the **exact same folder name** (e.g., `purchase_request`) but in different paths inside your `addons_path` (e.g., one in `eqnaa/` and one in `atheer/`), Odoo will **only load the first one it finds** based on the order in `odoo.conf`.

This leads to confusing errors such as:
1. `psycopg2.errors.UndefinedColumn: column ... does not exist` (because python fields from the first module are loaded, but the database wasn't updated).
2. `Field ... does not exist` during view validation (because views from the second module exist in the database, but its python model was replaced by the first module).

## ✅ Solution
- **Never name custom modules with generic names** like `purchase_request`. Always prefix them with your project or company name (e.g., `atheer_purchase_request`, `eqnaa_purchase_request`).
- If you encounter this, rename one of the module folders, update its `__manifest__.py`, and install it as a separate module. You may need to clean up the old views manually from the database if they cause update failures.
