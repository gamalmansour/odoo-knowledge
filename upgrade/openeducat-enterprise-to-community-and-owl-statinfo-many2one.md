# Migrating Custom Modules off `openeducat_core_enterprise` (`op.course.category`) & Fixing OWL `statinfo` on `Many2one`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `openeducat_core_enterprise`, `openeducat_core`, `op.category`, `op.course.category`, `statinfo`, `OWL`, `sale_crm`

---

## Problem

> 1. Installing a custom OpenEduCat addon fails with:
>    `You try to install module '<module>' that depends on module 'openeducat_core_enterprise'. But the latter module is not available in your system.`
> 2. After removing the Enterprise dependency, opening `sale.order` crashes in Odoo 16/17+ OWL because a smart button uses `<field name="batch_id" widget="statinfo"/>` on a `Many2one` field.

## Root Cause

1. Many custom OpenEduCat training addons list `openeducat_core_enterprise` in `depends` solely to reference `op.course.category`, even though Community `openeducat_core` already ships `op.category` (`name`, `code`, views, and ACLs). Worse, dropping an unmigrated `openeducat_core_enterprise` into Odoo 17 pulls `gamification`, `website`, and deprecated `web.assets_qweb` bundles.
2. In Odoo 16/17+ OWL (`addons/web/static/src/views/fields/stat_info/stat_info_field.js`), `StatInfoField` enforces `supportedTypes: ["float", "integer", "monetary"]` and resolves a numeric formatter by field type; binding `widget="statinfo"` to a `Many2one` crashes form rendering.

## Solution ✅

1. **Replace `op.course.category` with `op.category` from `openeducat_core` Community** and drop `openeducat_core_enterprise` from `__manifest__.py` (adding `sale_crm` whenever `sale.order.opportunity_id` is referenced).
2. **Replace `Many2one` `statinfo` with a computed `Integer` count field:**

```python
training_batch_count = fields.Integer(
    string='Batches',
    compute='_compute_training_batch_count',
)
```

```xml
<button name="action_view_batch"
        type="object"
        class="oe_stat_button"
        icon="fa-graduation-cap"
        invisible="training_batch_count == 0">
    <field name="training_batch_count" widget="statinfo" string="Batches"/>
</button>
```

3. **Refresh cached module dependencies** before installing from the UI (**Apps → Update Apps List**) or install via CLI (`-i <module>`), because Odoo caches `ir.module.module.dependency` rows in PostgreSQL from previous manifest scans.

## ⚠️ Pitfalls

- **Cached `ir_module_module_dependency` rows:** Editing `__manifest__.py` on disk does NOT clear the missing dependency error in the Apps UI until **Update Apps List** is clicked (or `-i` is run from CLI).
- **CRM → Quotation Pre-fill Seam:** Override `_prepare_opportunity_quotation_context()` on `crm.lead` (from `sale_crm`) in addition to `@api.model_create_multi def create(self, vals_list)` so clicking **New Quotation** on an Opportunity pre-fills the unsaved form before saving.
- **Multi-Addon `SaleOrder.action_confirm()` Collisions:** When co-installed with line-level batch provisioning addons (e.g., `dvst_automatic_admission`), check existing line/order batches after `super().action_confirm()` before creating a header-level fallback batch.

## Verification

```bash
./odoo-bin -c <conf> -d <db> -i <module> --stop-after-init
```

## References

- Core reference: `addons/web/static/src/views/fields/stat_info/stat_info_field.js`
- Core reference: `addons/sale_crm/models/crm_lead.py` (`_prepare_opportunity_quotation_context`)
