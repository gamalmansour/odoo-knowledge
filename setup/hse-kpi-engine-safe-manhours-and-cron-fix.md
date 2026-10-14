# HSE KPI Engine: Safe Man-Hours, Leading Indicators, Cron Project State Fix, and Dashboard Views

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `kpi`, `dashboard`, `cron`, `ltifr`, `trir`, `safe-man-hours`, `search-view`, `empty-recordset`, `entry-date`

---

## Problem

When navigating to **Safety > Dashboard** or **Safety > Reporting > KPI Engine**, the screens were empty (0 records), graphs rendered blank, and pivot tables were empty. Additionally:
1. The automated cron `ir_cron_hse_kpi_generator` intended to generate monthly KPIs was failing silently or raising `ValueError: Invalid field 'status' on model 'construction.project'` because it filtered by `('status', '=', 'active')` instead of `('state', '=', 'active')`.
2. `action_hse_kpi_dashboard` used `context="{'search_default_year': ...}"`, but `hse_kpi_views.xml` lacked a `<search>` view entirely, so no filter existed to match the default key.
3. Reading `ir.config_parameter` for `ltifr_base` did not use `.sudo()`, risking `AccessError` for standard safety users.
4. Man-hours computation only inspected `project.work.order` labor lines and omitted distributed `construction.labor.sheet` records.
5. Safety managers had no tracking for **Safe Man-Hours** (hours worked without LTI) or leading indicators (BBS safe act ratios and site inspections).
6. **Empty Recordset Truthiness Trap (`if Observation:`):** Assigning `Observation = self.env['hse.observation'] if 'hse.observation' in self.env else None` returns an empty recordset `hse.observation()`, whose truthiness `bool(Observation)` is `False` in Odoo ORM. Checking `if Observation:` or `if Inspection:` always evaluated to `False`, leaving `observation_count` and `inspection_count` permanently at `0`.
7. **Historical Man-Hours Clustering in Current Month (`entry_date` Default Override):** When `project.labor.record.entry_date` overrides a base field (which had `default=fields.Date.context_today`) with `compute='_compute_entry_date', store=True, readonly=False`, leaving the inherited default (or setting `default=False`) causes Odoo's `add_default_values()` to inject `'entry_date'` into `vals_list` during `create()`, bypassing `_compute_entry_date` and stamping historical labor lines with today's date.

## Root Cause

1. **Model Field Mismatch in Automation:**
   `construction.project` uses `state` for its lifecycle stages (`draft`, `active`, `completed`), not `status`.
2. **Missing Search View:**
   Odoo window actions with `search_default_*` require a matching filter `name="..."` inside an explicit search view. Without it, the search bar defaults to generic name search.
3. **Un-sudoed Config Parameter:**
   `ir.config_parameter` is restricted to administrative groups. Any compute method evaluated in the session of a standard employee will crash without `.sudo()`.
4. **Empty Recordset Evaluates to `False`:**
   In Odoo ORM, `bool(env['model.name'])` is `False` because `len(recordset) == 0`. Checking `if Model:` instead of `if Model is not None:` silently skips the block.
5. **`default=None` Required on Editable Computed Field Overrides:**
   In Odoo's `fields.py`, `default=False` is treated as a literal default value (`False`), whereas `default=None` is the sentinel for "no default". Only `default=None` prevents `add_default_values()` from pre-populating a `readonly=False` computed field on `create()`.

## Solution ✅

### 1. Fix Cron Query, Empty Recordset Check, and Add Safe Man-Hours / Leading Indicators
In `construction_hse/models/hse_kpi.py`:

```python
class HseKpi(models.Model):
    _name = 'hse.kpi'
    _description = 'HSE KPI Engine'

    safe_man_hours = fields.Float(string='Safe Man-Hours', compute='_compute_kpis', store=True)
    observation_count = fields.Integer(string='Observations (BBS)', compute='_compute_kpis', store=True)
    safe_act_ratio = fields.Float(string='Safe Behavior Ratio (%)', compute='_compute_kpis', store=True)
    inspection_count = fields.Integer(string='Inspections Conducted', compute='_compute_kpis', store=True)

    # Inside _compute_kpis():
    # FIX: Use 'is not None' because self.env['hse.observation'] is an empty recordset (bool == False)
    if Observation is not None:
        obs = Observation.search([
            ('project_id', '=', rec.project_id.id),
            ('observation_date', '>=', date_start),
            ('observation_date', '<', date_end)
        ])
        rec.observation_count = len(obs)
```

### 2. Clear Inherited Default on `project.labor.record.entry_date`
In `construction_labor/models/labor_sheet.py`:

```python
    entry_date = fields.Date(
        compute='_compute_entry_date', store=True, readonly=False,
        default=None,
        help="Date this labor was incurred — from the labor sheet, else the work order."
    )
```

### 3. Add Dedicated Search View in XML
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

- **Never Use `if Model:` on `self.env['model']`:**
  Always use `if Model is not None:` when checking optional models resolved from `self.env`, because an empty Odoo recordset is falsy (`bool(recordset) is False`).
- **Use `default=None` (Not `default=False`) to Clear Inherited Field Defaults:**
  When overriding a field that had a `default` in the parent model with `compute='...', store=True, readonly=False`, set `default=None` so Odoo does not pre-fill the field during `create()` and skip the compute method.
- **Avoid `widget="percentage"` on Pre-Scaled `0..100` Fields:**
  In Odoo 16+, `widget="percentage"` multiplies the stored float by `100`. Only use `widget="percentage"` on `0.0..1.0` ratio fields (like `training_compliance`), not on `0.0..100.0` fields (like `safe_act_ratio`).

## Verification

```bash
# Check KPI records in database
python -c "
import odoo
from odoo import api, SUPERUSER_ID
with odoo.registry('cons_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('HSE KPIs count:', env['hse.kpi'].search_count([]))
"
```

## References

- Related models: `construction_hse/models/hse_kpi.py`, `construction_labor/models/labor_sheet.py`
- Related views: `construction_hse/views/hse_kpi_views.xml`
- Cron job: `construction_hse/data/hse_cron.xml`
