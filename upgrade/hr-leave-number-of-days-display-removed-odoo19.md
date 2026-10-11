# hr.leave.number_of_days_display removed in Odoo 19 — use duration_display

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `migration`, `hr_holidays`, `hr.leave`, `number_of_days_display`, `duration_display`, `qweb`, `portal`

---

## Problem

A QWeb template (portal page, report, or backend view) that reads
`hr.leave.number_of_days_display` raises a 500 while rendering on Odoo 19:

```
500: Internal Server Error
The error occurred while rendering the template `solargy_hr_portal.portal_my_timeoffs`
and evaluating the following expression: `<span t-esc="leave.number_of_days_display"/>`

AttributeError: 'hr.leave' object has no attribute 'number_of_days_display'
```

Same crash shape for any code path (`t-esc`, `t-field`, Python `leave.number_of_days_display`).

## Root Cause

Older Odoo (≤15) exposed `number_of_days_display` on `hr.leave` as a Float
"Duration in days". It was dropped in later versions. In **Odoo 19**
`hr.leave` exposes instead (`addons/hr_holidays/models/hr_leave.py`):

- `number_of_days` — `fields.Float('Duration (Days)')`, the raw numeric days.
- `number_of_hours` — `fields.Float('Duration (Hours)')`.
- `duration_display` — `fields.Char('Requested', compute='_compute_duration_display', store=True)`.
  Unit-aware human string: `"2 days"` for day-based types, `"3:00 hours"` for
  hour-based types (`leave_type_request_unit == 'hour'`).

There is **no** `number_of_days_display`, so any template migrated forward
verbatim crashes the moment a row is rendered.

## Solution ✅

Prefer `duration_display` — it already includes the unit and handles
hour-based leave types, so drop any hardcoded " Days"/" Hours" suffix:

```xml
<!-- BEFORE (500 on Odoo 19) -->
<span t-esc="leave.number_of_days_display"/> Days

<!-- AFTER (unit-aware, no crash) -->
<span t-esc="leave.duration_display"/>
```

If you specifically need the numeric days only (and the leave types are all
day-based), use `number_of_days` and format it so you don't render `2.0`:

```xml
<span t-esc="'%g' % leave.number_of_days"/> Days
```

## ⚠️ Pitfalls

- Do **not** keep a hardcoded " Days" next to `duration_display` — you'd get
  `"2 days Days"`. Remove the suffix; the field carries its own unit.
- `number_of_days` on an **hour-based** leave type shows a confusing fraction
  (a 2-hour leave → `0.25`). Use `duration_display` to stay correct across units.
- Grep the whole module — the removed name often appears in more than one place
  (list/kanban/report/portal): `grep -rn number_of_days_display <module>`.
- Add a cheap regression test: assert `'number_of_days_display' not in
  env['hr.leave']._fields` so nobody reintroduces it on the next migration.

## Verification

```bash
# Confirm the field is gone and the replacement exists in the running version
grep -nE "number_of_days_display|duration_display|number_of_days =" \
  addons/hr_holidays/models/hr_leave.py
# Reload the module, open the page/report — renders without the 500.
```

## References

- Fixed in: `solargy/solargy_hr_portal/views/portal_templates.xml` (`portal_my_timeoffs`)
- Core field: `addons/hr_holidays/models/hr_leave.py` → `_compute_duration_display`
- Related file: `upgrade/crm-lead-mobile-field-removal.md`
- Related file: `upgrade/hr-employee-address-home-id-deprecation-odoo17.md`
