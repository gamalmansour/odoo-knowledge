# Odoo 18 Enterprise Gantt Empty Date Window & Scales Gotchas

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `gantt`, `web_gantt`, `enterprise`, `dates`, `scales`, `empty-view`, `focus-date`

---

## Problem

When opening an Enterprise Gantt view (e.g., Project Schedule Phases, Operations, or Planning Slots), the screen renders completely blank showing "No records yet" / empty canvas, despite having valid records populated in the database.

```
POST /web/dataset/call_kw/project.schedule.phase/get_gantt_data 200 - []
```

The user assumes data corruption or a broken view architecture, even though `ir.ui.view` installs cleanly without errors.

---

## Root Cause

1. **Date Horizon & Focus Date Blindspot (`_getDefaultFocusDate`):**
   In Odoo Enterprise (`web_gantt`), the Gantt component computes its initial viewport window around `focusDate = DateTime.local()` (i.e. `Today`). When `default_scale="month"` is used, `web_gantt` requests only records intersecting the current month:
   ```python
   domain = [
       (date_start_field, '<=', stop_date),
       (date_stop_field, '>=', start_date),
   ]
   ```
   If all existing records in the database have their dates planned in the past (e.g. ended 2 months ago) or far into the future, the query returns zero rows for the initial viewport, rendering an empty Gantt chart until the user manually navigates backwards/forwards in the time navigator.

2. **Unsupported Scale Tokens in XML (`scales`):**
   In `gantt_arch_parser.js`, scales are parsed against the hardcoded `SCALES` dictionary:
   - Valid scales in Odoo 18: `day`, `week`, `week_2`, `month`, `month_3`, `year`.
   - Specifying non-standard tokens like `quarter` (`scales="week,month,quarter,year"`) causes `SCALES[key]` to be `undefined`, which silently drops the scale option.

3. **Missing Popover Template & Search View Binding:**
   Without `<templates><div t-name="gantt-popover">`, hovering over Gantt pills provides minimal or no context (e.g., Float, Critical Path, Predecessors). Furthermore, if the act_window fails to bind `search_view_id` with `group_by`, items cannot be easily grouped by parent project or filtered by critical state.

---

## Solution ✅

### 1. Configure Supported Scales and Rich Popover in View Arch

```xml
<record id="view_schedule_phase_gantt" model="ir.ui.view">
    <field name="name">project.schedule.phase.gantt</field>
    <field name="model">project.schedule.phase</field>
    <field name="arch" type="xml">
        <gantt date_start="date_start"
               date_stop="date_end"
               default_group_by="project_id"
               dependency_field="depends_on_ids"
               dependency_inverted_field="successor_ids"
               color="color"
               string="Project Schedule"
               default_scale="month"
               scales="day,week,month,year">
            <templates>
                <div t-name="gantt-popover">
                    <div><strong>Project: </strong><t t-esc="project_id[1]"/></div>
                    <div><strong>Phase: </strong><t t-esc="name"/></div>
                    <div>
                        <t t-esc="date_start.toFormat('yyyy-MM-dd')"/>
                        <i class="fa fa-long-arrow-right mx-1" title="Arrow"/>
                        <t t-esc="date_end.toFormat('yyyy-MM-dd')"/>
                    </div>
                    <div><strong>Status: </strong><t t-esc="state"/></div>
                    <div><strong>Total Float: </strong><t t-esc="total_float"/> days</div>
                    <div t-if="is_critical" class="text-danger fw-bold mt-1">
                        <i class="fa fa-exclamation-triangle me-1"/> Critical Path
                    </div>
                </div>
            </templates>
            <field name="name"/>
            <field name="project_id"/>
            <field name="date_start"/>
            <field name="date_end"/>
            <field name="is_critical"/>
            <field name="total_float"/>
            <field name="state"/>
        </gantt>
    </field>
</record>
```

### 2. Bind Search View and Default Grouping in Window Action

```xml
<record id="action_schedule_phase_gantt" model="ir.actions.act_window">
    <field name="name">Project Schedule (Gantt)</field>
    <field name="res_model">project.schedule.phase</field>
    <field name="view_mode">gantt,list,form</field>
    <field name="search_view_id" ref="view_project_schedule_phase_search"/>
    <field name="context">{'search_default_group_project': 1}</field>
</record>
```

### 3. Ensure Continuous Operational Coverage in Seeded Data

Ensure project schedules include active operational / closeout / maintenance phases that span through the current date (`DateTime.local()`), or set `default_scale="year"` so the entire project lifecycle is immediately visible upon initial load.

---

## ⚠️ Pitfalls

- **Do NOT use `quarter` in `scales="..."`**: Use `month` or `year`.
- **M2M Inverse for Dependencies**: `dependency_inverted_field` must point to an explicit Many2many field with inverted column ordering on the same relation table (e.g. `depends_on_ids` vs `successor_ids`).
- **Color Field Computation**: Compute fields driving `color="..."` should be `store=True` with `@api.depends` for instant rendering without N+1 compute bottlenecks in large Gantt hierarchies.

---

## Verification

1. Query records covering the current date:
   ```python
   today = fields.Date.today()
   active = env['project.schedule.phase'].search([('date_start', '<=', today), ('date_end', '>=', today)])
   assert len(active) > 0
   ```
2. Navigate to the Gantt view in the web client: Gantt pills immediately render across project groups without needing to click navigation arrows.
3. Hover over a pill: rich popover displays project, phase, dates, float, and critical path badge.
