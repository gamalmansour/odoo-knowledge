# Contract Expiry Alerts: Window-Based Beats the Core's Exact-Date Matching

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc (hr)                                  |
| Odoo Versions | 19 (core method verified; pattern applies to all) |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr`, `contract`, `expiry`, `cron`, `notification`, `hr.version`, `alert`

---

## Problem

> Client wants "alert HR X days before an employee's contract ends". Odoo 19 core already
> has `hr.employee.notify_expiring_contract_work_permit()` driven by
> `res.company.contract_expiration_notice_period` — but it has gaps for this requirement.

## Root Cause

The core method matches the **exact** date:
`('contract_date_end', '=', today + notice_period)`. Consequences:
- If the cron server was down that one day, the alert is silently lost forever.
- A contract created/edited with less than `notice_period` remaining never matches.
- It notifies only `hr_responsible_id` (a single user) via an activity, not a team.

## Solution ✅

Implement a window-based cron with a date-marker for dedup (not a boolean):

```python
employees = self.search([
    ('contract_date_end', '>=', today),
    ('contract_date_end', '<=', today + timedelta(days=notice)),
]).filtered(lambda e: e.contract_end_notified_date != e.contract_date_end)
...
employee.contract_end_notified_date = employee.contract_date_end  # after notifying
```

- The `>= today` + `<= today+notice` **window** self-heals after missed cron days.
- Storing the **notified end date** (instead of a boolean) makes contract renewal
  automatically re-arm the alert: new `contract_date_end` ≠ stored marker → notify again.
- Notify a security group's `all_user_ids.partner_id` via `message_notify` so the whole
  HR team sees it; imply the group from `hr.group_hr_manager`.

## ⚠️ Pitfalls

- `contract_date_end` / `contract_date_start` on `hr.employee` (Odoo 19) are **related,
  non-stored** fields living on `hr.version` — SQL verification must join
  `hr_version v on v.id = e.current_version_id`; ORM domains work fine.
- `ir.cron` has no `name` column in 19 — use `cron_name` (name lives on the inherited
  `ir.actions.server`).
- If the core cron is also active, HR may get both the group notification and the
  single-user activity — decide whether to keep both or archive the core one.

## Versions

Verified on Odoo 19.0.
