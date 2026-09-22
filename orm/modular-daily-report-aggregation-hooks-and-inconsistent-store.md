# Modular Daily Site Report Aggregation via Extension Hooks and Odoo 18 Inconsistent Store Computes

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `architecture`, `daily-report`, `hooks`, `inheritance`, `inconsistent-store`, `warning`, `odoo18`

---

## Problem

When designing a centralized site operational report (e.g. `project.daily.report`) that aggregates metrics from independent sibling modules (`construction_equipment`, `construction_store_issue`, `construction_waste`):

1. **Circular Dependency Trap:** Having the core project module depend on downstream specialized modules introduces circular dependencies (`construction_equipment` -> `construction_project` -> `construction_equipment`).
2. **Registry Crash on Stale/Cross-Module Field Names in `@api.depends`:** Referencing a field from an inherited model that was renamed or misspelled (e.g. `@api.depends('waste_record_ids.is_over_allowance')` instead of `is_waste_exceeded`) causes an immediate registry load failure:
   ```
   ValueError: Wrong @depends on '_compute_waste_kpis' ... Dependency field 'is_over_allowance' not found in model construction.waste.record.
   ```
3. **Odoo 18 Registry UserWarning for Inconsistent Store:** Combining stored computed metrics (`store=True`) with non-stored UI alert banners (HTML fields) in the SAME `@api.depends` compute method triggers:
   ```
   UserWarning: project.daily.report: inconsistent 'store' for computed fields, accessing waste_warning may recompute and update waste_record_count... Use distinct compute methods for stored and non-stored fields.
   ```

## Root Cause

- Odoo registry dependency tree validates every field path in `@api.depends` at server start (`preload_registries`).
- Mixing stored and non-stored fields in the same compute method violates Odoo 18 cache invalidation contracts because reading an un-stored field from UI triggers write/flush logic on the stored fields in cache.

## Solution ✅

### 1. In Core Model (`construction_project`): Provide an Extension Hook

```python
class ProjectDailyReport(models.Model):
    _name = 'project.daily.report'
    
    def action_fetch_daily_activities(self):
        for rec in self:
            # Fetch core work orders & manpower...
            rec._hook_fetch_daily_activities()

    def _hook_fetch_daily_activities(self):
        """Modular hook for sibling modules to pull their records."""
        pass
```

### 2. In Sibling Modules (`construction_equipment`, `construction_waste`, etc.): Inherit and Separate Computes

```python
class ProjectDailyReport(models.Model):
    _inherit = 'project.daily.report'

    fuel_log_ids = fields.Many2many('construction.equipment.fuel.log', ...)
    total_fuel_liters = fields.Float(compute='_compute_equipment_kpis', store=True)
    has_abnormal_fuel_consumption = fields.Boolean(compute='_compute_equipment_kpis', store=True)

    # Distinct compute method for non-stored HTML banner!
    abnormal_fuel_warning = fields.Html(compute='_compute_abnormal_fuel_warning')

    @api.depends('fuel_log_ids.liters', 'fuel_log_ids.is_consumption_abnormal')
    def _compute_equipment_kpis(self):
        for rec in self:
            rec.total_fuel_liters = sum(rec.fuel_log_ids.mapped('liters'))
            rec.has_abnormal_fuel_consumption = any(rec.fuel_log_ids.mapped('is_consumption_abnormal'))

    @api.depends('has_abnormal_fuel_consumption', 'fuel_log_ids.equipment_id')
    def _compute_abnormal_fuel_warning(self):
        for rec in self:
            if rec.has_abnormal_fuel_consumption:
                rec.abnormal_fuel_warning = "<div class='alert alert-danger'>...</div>"
            else:
                rec.abnormal_fuel_warning = False

    def _hook_fetch_daily_activities(self):
        super()._hook_fetch_daily_activities()
        for rec in self:
            logs = self.env['construction.equipment.fuel.log'].search([
                ('project_id', '=', rec.project_id.id),
                ('date', '=', rec.report_date)
            ])
            rec.fuel_log_ids = [(6, 0, logs.ids)]
```

## ⚠️ Pitfalls

- Never mix `store=True` and un-stored fields in the same compute method in Odoo 18.
- Always verify field names on the target comodel before declaring `@api.depends('relation_ids.field_name')`.
- Keep relational Many2many relations on inheriting modules with explicit table names to avoid collision.

## Verification

Run Odoo server upgrade:
```bash
odoo-bin -c odoo.conf -d mydb -u construction_project,construction_equipment,construction_waste --stop-after-init
```
Must load registry with exit code 0 and zero UserWarnings.
