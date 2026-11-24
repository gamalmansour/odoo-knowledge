# Odoo 20.0 API & Security Breaking Changes (Verified Live)

- **Category:** `upgrade`
- **Odoo Versions:** `20.0`
- **Last Verified:** `2026-11-24`

## Problem / Symptoms
When building or migrating custom modules to Odoo 20.0, several core models and fields changed compared to Odoo 17–19:
1. `KeyError: 'ir.rule'` when loading security XML.
2. `ValueError: Invalid field 'report_file' in 'ir.actions.report'`.
3. `TypeError: <field>: use BinaryValue instead of bytes` when assigning `base64.b64encode(...)` bytes to `fields.Binary`.
4. `ValueError: Wrong value for product.template.tracking: 'none'`.
5. `AttributeError: 'ir.config_parameter' object has no attribute 'set_param'` / Down Payment account configuration changed.
6. `ValueError: Invalid field 'company_registry' in 'res.company'`.

## Solution ✅
1. **Unified `security/ir.access.csv`:** Odoo 20 merges `ir.model.access.csv` and `ir.rule` into `security/ir.access.csv` with columns: `id,name,model_id,group_id/id,operation,domain`. Example multi-company rule:
   `rule_my_model_company,My Model Multi-Company,my.model,,crud,"[('company_id', 'in', company_ids)]"`
2. **Reports:** Remove `<field name="report_file">` from `ir.actions.report` records; only `report_name` is used.
3. **Binary Fields:** Pass base64 ASCII `str` (`.decode('ascii')`) or `BinaryValue` instead of raw `bytes`.
4. **Product Tracking:** Omit `tracking` (or leave `False`) for untracked products instead of `'none'`; valid tracked values remain `'lot'` / `'serial'`.
5. **Down Payment Account:** Set `company.downpayment_account_id` directly on `res.company` (no legacy `sale.default_deposit_product_id` config param needed).
6. **Inventory Valuation:** `product.category.property_valuation` uses `'periodic'` vs `'real_time'` (Perpetual at invoicing) with accrual accounts (`property_account_invoiced_not_delivered_id` → `Deferred Revenue`).
7. **OWL 3 Reactive State & Templates:** `useState` is removed in Odoo 20 OWL 3 — import `proxy` and `useProps` from `@odoo/owl` (with `standardActionServiceProps` from `@web/webclient/actions/action_plugin`), declare `this.state = proxy({...})`, and **prefix ALL component properties, getters, and handlers in XML templates with `this.`** (e.g. `this.state.xxx`, `this.myMethod` — bare `state.xxx` throws `TypeError: Cannot read properties of undefined`).
8. **Stock Move UoM:** `stock.move` no longer accepts `product_uom` in `create()` (defaults automatically from `product_id.uom_id`).
9. **Bundled SCSS Assets:** Never put `@import url(...)` (e.g., Google Fonts) inside a `.scss` file loaded in `web.assets_backend` — CSS `@import` mid-bundle breaks the entire compiled backend stylesheet.

## ⚠️ Pitfalls
- Always keep `addons/` (Community) and `enterprise-20.0/` synced to the same date; mismatched commits cause missing XML ID errors in `account_reports` (`account.account_tag_adj_depreciation_and_amortization`).
- `.po` translation files in Odoo 20 strictly require `#. module: <module_name>` headers above every `msgid` entry.
