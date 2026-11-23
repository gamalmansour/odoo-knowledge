# Odoo 19 `hr.leave.create()` Calling `_compute_duration()` Under Portal User Raises `AccessError` on `resource.calendar.attendance` and `hr.leave.write`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.leave`, `portal`, `resource.calendar.attendance`, `_compute_duration`, `AccessError`, `odoo-sh`, `ci`

---

## Problem

On newer Odoo 19 builds (e.g. Odoo.sh CI), creating an `hr.leave` record as a `base.group_portal` user (with `perm_read=1, perm_create=1, perm_write=0`) fails with `AccessError` even when the portal user has proper ACLs on `hr.leave`, `hr.employee`, and `hr.version`:

```
odoo.exceptions.AccessError: You are not allowed to access 'Work Detail' (resource.calendar.attendance) records.
```

And if only `resource.calendar.attendance` read ACL is added, a direct `leave._compute_duration()` call under the portal user next fails on `leave.number_of_hours = hours` because assigning a stored field outside ORM `protecting()` triggers `hr.leave.write()`, which portal users do not have.

## Root Cause

Stored computed fields (`number_of_days`, `number_of_hours`) automatically run with `compute_sudo=True` and field protection when triggered lazily by the ORM. However, newer Odoo 19 core calls `holidays._compute_duration()` **explicitly** inside `hr.leave.create()` under the active user (`portal_user`) without `.sudo()`. This bypasses `compute_sudo=True`, causing:
1. `_get_durations()` → `resource.calendar._attendance_intervals_batch()` → `self.env['resource.calendar.attendance'].search(...)` to fail with `AccessError` for `base.group_portal`.
2. Direct assignment `leave.number_of_hours = hours` inside `_compute_duration()` to fall back to `leave.write(...)` under `portal_user` (`perm_write=0`).

## Solution ✅

1. **Restore `compute_sudo` semantics in custom `hr.leave` overrides:**

```python
def _compute_duration(self) -> None:
    super(HrLeave, self.sudo())._compute_duration()

def _get_durations(self, check_leave_type: bool = True, resource_calendar=None) -> dict:
    cal_arg = resource_calendar.sudo() if resource_calendar else None
    result = super(HrLeave, self.sudo())._get_durations(
        check_leave_type=check_leave_type,
        resource_calendar=cal_arg,
    )
    ...
```

2. **Grant least-privilege read ACLs + strict record rules in portal HR modules (for standalone installs):**
- Add read-only (`1,0,0,0`) ACLs in `ir.model.access.csv` for `base.group_portal` on `resource.model_resource_calendar`, `resource.model_resource_calendar_attendance`, `resource.model_resource_calendar_leaves`, and `resource.model_resource_resource` (and add `'resource'` to `__manifest__.py` `depends`).
- Add `ir.rule` restrictions in `security/security.xml` so portal users can ONLY read their own `resource.resource` (`[('user_id', '=', user.id)]`) and global holidays or their own `resource.calendar.leaves` (`['|', ('resource_id', '=', False), ('resource_id.user_id', '=', user.id)]`).

## ⚠️ Pitfalls

- **Never grant unrestricted read on `resource.calendar.leaves` or `resource.resource` to `base.group_portal`**: without `ir.rule` domain filters, portal users could inspect other employees' leave dates via RPC.
- **Test on a fresh DB (without demo/client data) before pushing to Odoo.sh**: fresh Odoo.sh CI databases also expose hidden test assumptions such as:
  - Default company calendar (`Standard 40 hours/week`) having a 1-hour `lunch` break that reduces `hr.attendance.worked_hours` by 1h unless the test assigns an explicit calendar.
  - Default `company.country_id = False` causing country-scoped `hr.payroll.structure` record rules to block non-superuser payroll officer tests unless `cls.company.country_id` matches `cls.structure.country_id`.
  - Modules converted from `post_init_hook` to manual server actions failing CI tests unless `setUpClass` invokes the server action first.

## Verification

```bash
# Simulate Odoo.sh fresh-DB CI run:
createdb -p 5433 ci_tmp
odoo-bin -c solargy.conf -d ci_tmp --without-demo=all \
  -i solargy_hr_portal,solargy_hr --test-enable \
  --test-tags /solargy_hr_portal,/solargy_hr --stop-after-init
dropdb -p 5433 ci_tmp
```

## References

- `solargy_hr/models/hr_leave.py`
- `solargy_hr_portal/security/ir.model.access.csv`
- `solargy_hr_portal/security/security.xml`
- `solargy_hr_portal/tests/test_portal.py`
