# HSE KPI Engine: Safe Man-Hours, Leading Indicators, Cron Project State Fix, and Dashboard Views

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `kpi`, `dashboard`, `cron`, `ltifr`, `trir`, `safe-man-hours`, `search-view`

---

## Problem

When navigating to **Safety > Dashboard** or **Safety > Reporting > KPI Engine**, the screens were empty (0 records), graphs rendered blank, and pivot tables were empty. Additionally:
1. The automated cron `ir_cron_hse_kpi_generator` intended to generate monthly KPIs was failing silently or raising `ValueError: Invalid field 'status' on model 'construction.project'` because it filtered by `('status', '=', 'active')` instead of `('state', '=', 'active')`.
2. `action_hse_kpi_dashboard` used `context="{'search_default_year': ...}"`, but `hse_kpi_views.xml` lacked a `<search>` view entirely, so no filter existed to match the default key.
3. Reading `ir.config_parameter` for `ltifr_base` did not use `.sudo()`, risking `AccessError` for standard safety users.
4. Man-hours computation only inspected `project.work.order` labor lines and omitted distributed `construction.labor.sheet` records.
5. Safety managers had no tracking for **Safe Man-Hours** (hours worked without LTI) or leading indicators (BBS safe act ratios and site inspections).

## Root Cause

1. **Model Field Mismatch in Automation:**
   `construction.project` uses `state` for its lifecycle stages (`draft`, `active`, `completed`), not `status`.
2. **Missing Search View:**
   Odoo window actions with `search_default_*` require a matching filter `name="..."` inside an explicit search view. Without it, the search bar defaults to generic name search.
3. **Un-sudoed Config Parameter:**
   `ir.config_parameter` is restricted to administrative groups. Any compute method evaluated in the session of a standard employee will crash without `.sudo()`.

## Solution ✅

### 1. Fix Cron Query and Add Safe Man-Hours / Leading Indicators
In `construction_hse/models/hse_kpi.py`:

```python
class HseKpi(models.Model):
    _name = 'hse.kpi'
    _description = 'HSE KPI Engine'

    safe_man_hours = fields.Float(string='Safe Man-Hours', compute='_compute_kpis', store=True)
    observation_count = fields.Integer(string='Observations (BBS)', compute='_compute_kpis', store=True)
    safe_act_ratio = fields.Float(string='Safe Behavior Ratio (%)', compute='_compute_kpis', store=True)
    inspection_count = fields.Integer(string='Inspections Conducted', compute='_compute_kpis', store=True)

    @api.model
    def action_generate_current_month(self) -> None:
        """Ensure current month KPI records exist for active projects."""
        today = fields.Date.context_today(self)
        y = today.year
        m = str(today.month)

        # FIX: query 'state', not 'status'
        projects = self.env['construction.project'].search([('state', '=', 'active')])
        for p in projects:
            existing = self.search([('project_id', '=', p.id), ('year', '=', y), ('month', '=', m)], limit=1)
            if not existing:
                existing = self.create({'project_id': p.id, 'year': y, 'month': m})
            existing.action_recalculate()

    @api.depends('man_hours', 'lti_count', 'recordable_count')
    def _compute_rates(self) -> None:
        base_rate = float(self.env['ir.config_parameter'].sudo().get_param('construction_hse.ltifr_base', '1000000.0'))
        for rec in self:
            if rec.man_hours and rec.man_hours > 0:
                rec.ltifr = round((rec.lti_count * base_rate) / rec.man_hours, 2)
                rec.trir = round((rec.recordable_count * 200000.0) / rec.man_hours, 2)
            else:
                rec.ltifr = 0.0
                rec.trir = 0.0
```

### 2. Add Dedicated Search View in XML
In `construction_hse/views/hse_kpi_views.xml`:

```xml
<record id="view_hse_kpi_search" model="ir.ui.view">
    <field name="name">hse.kpi.search</field>
    <field name="model">hse.kpi</field>
    <field name="arch" type="xml">
        <search string="Search HSE KPIs">
            <field name="name"/>
            <field name="project_id"/>
            <field name="year"/>
            <separator/>
            <filter string="Current Year" name="year" domain="[('year', '=', context_today().strftime('%Y'))]"/>
            <filter string="Zero LTI (Safe Projects)" name="zero_lti" domain="[('lti_count', '=', 0)]"/>
            <filter string="Has Recordable Incidents" name="has_incidents" domain="[('recordable_count', '>', 0)]"/>
            <group expand="0" string="Group By">
                <filter string="Project" name="group_by_project" context="{'group_by': 'project_id'}"/>
                <filter string="Year" name="group_by_year" context="{'group_by': 'year'}"/>
                <filter string="Month" name="group_by_month" context="{'group_by': 'month'}"/>
            </group>
        </search>
    </field>
</record>
```

## ⚠️ Pitfalls

- **Do Not Trust Field Names Across Modules:**
  Never assume a foreign model has `status` vs `state`. Always check the definition or `_fields` dictionary before writing domain filters.
- **Config Parameters Require Sudo:**
  Any user evaluating compute methods that read `ir.config_parameter` will hit permissions barriers unless `env['ir.config_parameter'].sudo()` is used.

## Verification

```bash
# Check KPI records in database
python -c "
import odoo
from odoo import api, SUPERUSER_ID
with odoo.registry('hadhoud_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('HSE KPIs count:', env['hse.kpi'].search_count([]))
"
```

## References

- Related models: `construction_hse/models/hse_kpi.py`
- Related views: `construction_hse/views/hse_kpi_views.xml`
- Cron job: `construction_hse/data/hse_cron.xml`
