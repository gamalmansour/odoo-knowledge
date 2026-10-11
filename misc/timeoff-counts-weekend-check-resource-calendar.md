# Time Off Counts Weekend Days → Fix the Working Schedule, Not the Code

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr_holidays`, `resource.calendar`, `working-schedule`, `weekend`, `number_of_days`, `configuration`, `egypt`

---

## Problem

> An employee requests time off Thursday → Sunday. The weekend is Friday + Saturday, so
> the request should count 2 working days — but Odoo counts 4. First instinct is to
> override `hr.leave` duration computation with custom code. **Don't.**

## Root Cause

Odoo already counts leave duration in **working days**: `hr.leave` derives
`number_of_days` from the employee's working schedule (`resource.calendar`) via
`_get_work_days_data_batch`. If weekend days are being counted, it is because the
calendar's attendance lines (`resource.calendar.attendance`) actually contain those days.

Typical causes found in practice:
- Someone edited "Standard 40 hours/week" and added rows for all 7 `dayofweek` values.
- Custom shift calendars ("08:30 to 04:30" etc.) created with a line for every day.
- Default US-style calendars (Mon–Fri) used in a Fri/Sat-weekend country: Thu→Sun then
  counts Thu+Fri = 2 days but the *wrong* 2 days.

## Solution ✅

Diagnose with SQL — one line tells you everything (`dayofweek`: 0=Mon … 4=Fri, 5=Sat, 6=Sun):

```sql
SELECT calendar_id, dayofweek, count(*)
FROM resource_calendar_attendance
GROUP BY 1, 2 ORDER BY 1, 2;
```

Fix through the ORM (recomputes dependents), removing the weekend rows:

```python
env['resource.calendar.attendance'].search([
    ('calendar_id', 'in', BROKEN_CALENDAR_IDS),
    ('dayofweek', 'in', ['4', '5']),   # Friday, Saturday
]).unlink()
```

Verify with a real computation before committing:

```python
data = employee._get_work_days_data_batch(thu_dt, sun_dt)[employee.id]
assert round(data['days']) == 2
```

## ⚠️ Pitfalls

- **Already-submitted leaves keep their stored `number_of_days`** — the fix applies to
  new computations. Decide explicitly whether to recompute pending (`confirm` /
  `validate1`) requests; do not silently rewrite validated history.
- Check `hour_from`/`hour_to` while you're there: hijacked calendars often carry absurd
  hours too (e.g. 08:00→23:00 = 15h/day), which corrupts hour-unit leaves,
  `hours_per_day` conversions, and payroll.
- UI path for the same fix: Employees → Configuration → Working Schedules → remove the
  weekend lines.
- Flexible-hours calendars (`flexible_hours=True`) don't use attendance lines — different
  logic applies.

## Versions

Verified on Odoo 19; the mechanism is the same in 15–18.
