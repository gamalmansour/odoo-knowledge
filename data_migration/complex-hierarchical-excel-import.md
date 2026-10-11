---
tags: [import, data migration, hierarchical data, odoo shell, pandas, translations]
author: "ENG/Gamal Mansour"
date: "2026-07-01"
odoo_version: "19.0"
---

# Handling Complex Hierarchical Excel Imports with Pandas and Odoo Shell

## Problem Definition
When importing Master Data for Customers and Suppliers from an Excel file, the structure may list Parent Companies (HQ) and Branches on separate rows but group them by a common identifier (e.g., `CODE`). Also, some rows act purely as "Contacts" (e.g., `branch responsible`). Standard Odoo XML-RPC or import tools might fail to accurately map translations (`jsonb` in Odoo 19) or properly structure the `is_company`, `parent_id`, and `type` fields.

## Solution ✅
A reliable way to import such hierarchical data with dynamic translations and tags is to use a python script executed via `odoo-bin shell`.

**Key steps:**
1. Use `pandas` to group by the common identifier (e.g., `CODE`).
2. Identify the HQ row (e.g., checking if `BRANCH NAME` is "HQ").
3. Create the **Parent Company** (`is_company=True`) first, assigning its `ref` to the `CODE`.
4. Create the **Branches** as child companies (`is_company=True`, `parent_id=Parent.id`).
5. Create the **Contacts** (`is_company=False`, `type='contact'`, `parent_id=ActiveParent.id`).
6. Map translation dynamically using `with_context(lang='ar_001').write({'name': ...})`.

**Execution:**
Run the script natively inside the Odoo environment:
```bash
/path/to/odoo-bin shell -c /path/to/odoo.conf -d <dbname> < import_script.py
```

## ⚠️ Pitfalls
- **Translation Fields:** In Odoo 19+, translated fields (`name`) are stored as `jsonb` in Postgres. Setting translations directly requires context manipulation rather than raw SQL (unless explicitly migrating schema).
- **Duplicate Prevention:** Always ensure your script checks for existing records using `env['res.partner'].search()` with `ref` or `name` before creating to make the script idempotent.
- **`is_company` confusion:** A branch should typically have `is_company=True` even if it has a `parent_id` (so it represents a sub-entity, not just a person).

## Last Verified
2026-07-01
