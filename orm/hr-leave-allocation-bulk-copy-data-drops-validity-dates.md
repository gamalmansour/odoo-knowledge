# hr.leave.allocation copy_data() Drops date_from and date_to on Bulk Child Creation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `hr_holidays`, `allocation`, `copy_data`, `date_from`, `date_to`, `bulk_allocation`, `validity`

---

## Problem

> When implementing bulk or multi-employee allocation patterns where a parent `hr.leave.allocation` record clones its values to child allocations via `copy_data()[0]` and `create()`, the validity dates (`date_from` and `date_to`) do not carry over as expected.
> Specifically, `date_to` is lost completely (becomes `False` / "No Limit"), and `date_from` resets to the approval day instead of inheriting the parent's start date.

## Root Cause

In Odoo core (`addons/hr_holidays/models/hr_leave_allocation.py`):

```python
date_from = fields.Date('Start Date', index=True, copy=False, default=fields.Date.context_today, ...)
date_to = fields.Date('End Date', copy=False, tracking=True)
```

1. **`copy=False` on both fields:** Odoo's ORM method `copy_data()` automatically filters out any field marked `copy=False`. As a result, neither `date_from` nor `date_to` is included in the dictionary returned by `copy_data()[0]`.
2. **`default=context_today` illusion:** Because `date_to` has no default, child records receive `False` (unlimited expiration). However, `date_from` possesses `default=fields.Date.context_today`. When child records are created without an explicit `date_from`, Odoo silently stamps today's date.
3. If the parent allocation is created and approved on the same day, `date_from` happens to match the parent by coincidence, creating the illusion that "only start date carried over while end date was lost". But if the parent allocation was scheduled for a future or past date (e.g., next year's leave cycle), the parent's `date_from` is lost too.

## Solution ✅

When duplicating or generating child records from a parent allocation dictionary, **explicitly inject `date_from` and `date_to`** into the values dictionary before calling `create()`:

```python
base_vals = self.copy_data()[0]
base_vals.update({
    'solargy_parent_allocation_id': self.id,
    'date_from': self.date_from,
    'date_to': self.date_to,
    # reset any target selector fields on children
    'employee_id': False,
})

children = self.create([
    dict(base_vals, employee_id=emp.id) for emp in targeted_employees
])
```

## ⚠️ Pitfalls

- **Expiring leaves become perpetual:** If an HR officer grants compensatory or annual leaves expiring on `31/12/2026`, dropping `date_to` leaves the child allocations with no expiry date ("No Limit"), allowing employees to take them years later.
- **Future allocations become active immediately:** If next year's allocation is generated in advance with `date_from = '2027-01-01'`, dropping `date_from` makes it effective immediately on creation date.
- **`copy_data()` cannot be trusted for all business fields:** Always check whether core models mark critical lifecycle or validity dates with `copy=False`.

## Verification

Run automated test verifying that child allocations inherit exact parent dates:

```python
def test_bulk_dates_carried_over_to_children(self):
    custom_start = date(2027, 1, 1)
    custom_end = date(2027, 12, 31)
    allocation = self._create_bulk(date_from=custom_start, date_to=custom_end)
    allocation.action_approve()
    children = allocation.solargy_child_allocation_ids
    self.assertTrue(all(c.date_from == custom_start for c in children))
    self.assertTrue(all(c.date_to == custom_end for c in children))
```

## References

- Related: `orm/hr-leave-allocation-bulk-double-action-error.md`
- Related: `orm/hr-leave-allocation-no-action-draft-reset-blocked.md`
