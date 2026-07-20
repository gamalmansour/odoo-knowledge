# Working-schedule-aware duration preview: reuse core compute via `hr.leave.new()` (don't re-implement)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `portal`, `hr_holidays`, `hr.leave`, `resource.calendar`, `working-hours`, `new`, `preview`, `dry`

---

## Problem

> A portal (or wizard/report) needs to show a leave's **number of days AND
> number of hours computed against the employee's Working Hours** — before the
> record is saved. The naive path is to re-implement the calendar math with
> `resource.calendar` internals, which is fragile (private methods move between
> versions — see `resource-calendar-working-day-api-odoo19.md`) and duplicates
> logic that core already gets right (half-days, public holidays, flexible
> employees, request unit, contract calendar).

## Root Cause

`hr.leave.number_of_days` / `number_of_hours` are **stored computes** driven by
`_compute_duration` → `_get_durations`, which already resolves the employee's
`resource_calendar_id` (from the contract/`hr.version`, else the company
calendar) and honours the working schedule. Re-deriving it by hand means
re-testing every edge case core already covers, and calling private
`resource.calendar` helpers that break on upgrade.

## Solution ✅

Compute on an **in-memory** record with `.new()` and read the stored-compute
fields back. `new()` writes nothing to the DB but runs the very same computes
`create()` would, so the preview equals the real result.

```python
# Controller — a plain GET returning JSON, called from the portal form's JS.
@route(['/my/timeoff/duration'], type='http', auth="user", website=True, methods=['GET'])
def portal_my_timeoff_duration(self, holiday_status_id=None, date_from=None, date_to=None, **kw):
    result = {'days': 0.0, 'hours': 0.0}
    employee = self._get_portal_employee()            # ownership via record rule
    try:
        leave_type_id = int(holiday_status_id or 0)
    except (TypeError, ValueError):
        leave_type_id = 0
    if employee and leave_type_id and date_from and date_to and date_from <= date_to:
        # sudo() only for the calendar math (resource.calendar is hidden from
        # portal users); no record is written.
        leave = request.env['hr.leave'].sudo().new({
            'holiday_status_id': leave_type_id,
            'employee_id': employee.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })
        result = {'days': round(leave.number_of_days, 2),
                  'hours': round(leave.number_of_hours, 2)}
    return request.make_json_response(result)
```

The fields that drive the calendar resolution are `employee_id` +
`request_date_from` + `request_date_to` (see
`hr.leave._compute_resource_calendar_id`, `@depends('employee_id',
'request_date_from', 'request_date_to')`). Setting those is enough; `date_from`
/ `date_to` and the durations cascade from them.

Front end: a classic frontend asset (`web.assets_frontend`) that self-guards to
the one form and `fetch()`es the route on `change`/`input`, with a sequence
counter to ignore out-of-order responses.

## ⚠️ Pitfalls

- **Don't** re-implement working-hours math with `resource.calendar` private
  methods — reuse the model's own compute. (`_get_calendars_attendance_intervals`
  doesn't even exist on 19.)
- `.new()` triggers computes but **not** SQL constraints / `@api.constrains`; it
  is a preview, not a validity check — the real `create()` still enforces rules.
- Portal users can't read `resource.calendar`; establish ownership with the
  user's own rights first (record rule), then `sudo()` **only** the compute.
- Odoo 19: `@route(type='json')` is a deprecated alias for `type='jsonrpc'`. A
  `type='http'` GET + `request.make_json_response(...)` sidesteps the JSON-RPC
  envelope and is trivial to call with `fetch`.
- Adding a **new** JS file to `assets` needs a **server restart**, not just
  `-u` (the manifest is cached in memory) — see
  `setup/manifest-assets-change-needs-server-restart.md`.

## Verification

```bash
grep -n "def _compute_resource_calendar_id\|def _compute_duration" addons/hr_holidays/models/hr_leave.py
# In a shell/test: new() over a full week resolves a calendar and positive figures
#   leave = env['hr.leave'].new({...}); assert leave.resource_calendar_id and leave.number_of_days > 0
```

## References

- Fixed in: `solargy/solargy_hr_portal` (`/my/timeoff/duration` + `portal_my_timeoff_new`)
- Related file: `orm/resource-calendar-working-day-api-odoo19.md`
- Related file: `orm/onchange-only-computation-breaks-nonform-create.md`
- Related file: `setup/manifest-assets-change-needs-server-restart.md`
- Core: `addons/hr_holidays/models/hr_leave.py` → `_get_durations`, `_compute_resource_calendar_id`
