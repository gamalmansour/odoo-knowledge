# Odoo 18 base_import Disallows Installed Module Name as External ID Prefix

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-13                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `base_import`, `external_id`, `xml_id`, `import_error`, `module_prefix`

---

## Problem

When importing records via the standard Odoo 18/19 Import Wizard (`base_import.import`) using an Excel or CSV file that contains an `id` (External ID) column, the dry-run or execution fails with the following validation error:

```text
The record <module>.<record_id> has the module prefix <module>. This is the part before the '.' in the external id. Because the prefix refers to an existing module, the record would be deleted when the module is upgraded. Use either no prefix and no dot or a prefix that isn't an existing module. For example, __import__, resulting in the external id __import__.<record_id>.
```

## Root Cause

In Odoo 18+, `base_import` adds strict protection for `ir.model.data` integrity. If an imported row specifies an External ID with a prefix matching an installed module (e.g. `construction_equipment.equip_01`), Odoo flags this because during a module upgrade (`-u module`), Odoo unlinks `ir.model.data` entries associated with that module that are not present in the module's declared XML/CSV data files. To prevent accidental data loss upon upgrade, Odoo blocks using installed module names in UI/wizard imports.

## Solution ✅

Use one of the following approaches when generating or preparing Excel/CSV templates with External IDs:

1. **Use a Custom Domain Prefix (Recommended):**  
   Use a prefix that does NOT match any installed module name, e.g.:
   - `construction_fleet.equip_cat_330d_01` (instead of `construction_equipment.equip_...`)
   - `construction_partner.client_nuca` (instead of `base.partner_...`)
   - `construction_master.cc_01_10`

2. **Use the Standard `__import__` Prefix:**  
   ```text
   __import__.equip_cat_330d_01
   ```

3. **Omit the Module Prefix Completely:**  
   Provide only the identifier without any dot (`.`):
   ```text
   equip_cat_330d_01
   ```
   Odoo will automatically prepend `__import__.` to the XML ID.

## ⚠️ Pitfalls

- **Existing Demo Data Updates:** If you intentionally want to update an existing record installed by a module XML file (e.g. updating a pre-installed record), verify whether the update should be done via module data upgrade or whether you should use the database ID column (`id` as integer) instead of External ID.
- **Related Many2one Lookups:** When referencing foreign records in related columns (e.g., `parent_id/id` or `product_id/id`), ensure that you use the exact matching prefix that was assigned when the target record was created.
