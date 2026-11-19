# Odoo 19 `hr.work.entry`: Writing `state='cancelled'` Silently Refuses Approved `hr.leave` Requests & `_error_checking` Re-Marks Archived Undefined Entries as `conflict`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.work.entry`, `hr_work_entry_holidays`, `hr.leave`, `action_refuse`, `conflict`, `hr_payroll`

---

## Problem

1. **Silent `OdooBot` Refusal of Validated Leaves:**
   During payslip work-entry regeneration or module upgrade cleanup, archiving conflicting `hr.work.entry` records with `work_entries.write({'active': False, 'state': 'cancelled'})` causes Odoo (`__system__` / `OdooBot`) to automatically refuse two-step approved (`state = 'validate'`) `hr.leave` requests linked via `leave_id`.
2. **Archived Rows Stuck in `active = False, state = 'conflict'` (Repeated Refusals):**
   Even after archiving a conflicting work entry whose `work_entry_type_id` was `False`/`NULL` (e.g., from a custom `hr.leave.type` like *Compensatory Days* created before linking a Work Entry Type), the archived row remains in `active = False, state = 'conflict'` in PostgreSQL, causing the linked leave to be refused **again** on every subsequent regeneration!

## Root Cause

1. **MRO Asymmetry Between `{'state': 'cancelled'}` and `{'active': False}`:**
   - `addons/hr_work_entry_holidays/models/hr_work_entry.py` overrides `write(vals)` **before** `super().write(vals)`:
     ```python
     def write(self, vals):
         if 'state' in vals and vals['state'] == 'cancelled':
             self.mapped('leave_id').filtered(lambda l: l.state != 'refuse').action_refuse()
         return super().write(vals)
     ```
   - Core Odoo (`addons/hr_work_entry/models/hr_version.py` & `hr_leave.py`) archives work entries by passing `{'active': False}` **without** `'state'` in `vals`. Base `addons/hr_work_entry/models/hr_work_entry.py` then sets `vals['state'] = 'cancelled'` *after* `hr_work_entry_holidays.write()` has already checked `'state' in vals`. Passing `'state': 'cancelled'` explicitly in `vals` triggers `action_refuse()` on every linked `hr.leave`.
2. **`_error_checking` `finally:` Block Overwriting Archived Undefined-Type Entries:**
   - When `write({'active': False})` runs without `hr_work_entry_no_check=True`, `HrWorkEntry._error_checking()` collects non-validated/non-cancelled entries before `yield`, archives them inside `yield`, and then executes `work_entries.exists()._check_if_error()` in `finally:`.
   - `_check_if_error()` runs `self.filtered(lambda b: not b.work_entry_type_id).write({'state': 'conflict'})` — which does **not** filter out `active = False` records, flipping the newly archived row right back to `state = 'conflict'` while `active = False`!

## Solution ✅

1. **Harden `HrWorkEntry` and `HrWorkEntryRegenerationWizard` at the model level:**
   - Filter out archived/cancelled rows in `HrWorkEntry._check_if_error()` so archiving undefined-type or validated-day entries never flips them back to `state='conflict'`.
   - In `HrWorkEntry.write()`, strip redundant `'state': 'cancelled'` when `'active': False` is passed together, and never allow `state='cancelled'` on already-inactive (`active=False`) records to refuse linked `hr.leave` records.
   - Add `'leave_id'` to `HrWorkEntryRegenerationWizard._work_entry_fields_to_nullify()` (matching core `'attendance_id'` and `'planning_slot_id'`) so `force=True` regeneration detaches `leave_id` on superseded rows.
   - Scope `HrLeave._regen_work_entries()` to `active_test=True` and deduplicate `(version_id, date)` slots so historical archived copies can never sum above 24h (`ValidationError`).
2. **Guard Payslip Force-Regeneration Around `validated` Days and Closed/Edited Payslips:**
   - Only run work-entry pre-generation on `state in ('draft', 'verify') and not edited` payslips.
   - Split `[date_from, date_to]` into contiguous unvalidated sub-ranges (`_iter_unvalidated_date_ranges`) before calling `generate_work_entries(..., force=True)` so `state='validated'` days never receive duplicate conflicting work entries.
   - Detach `leave_id` and archive using `{'active': False}` (never `'state': 'cancelled'`) under `with_context(hr_work_entry_no_check=True)`:

```python
@api.model
def _archive_conflicting_work_entries_safely(self, work_entries: models.Model) -> None:
    targets = work_entries.sudo().filtered(lambda we: we.state != 'validated')
    if not targets:
        return
    linked = targets.filtered('leave_id')
    if linked:
        linked.with_context(hr_work_entry_no_check=True).write({'leave_id': False})
    targets.with_context(hr_work_entry_no_check=True).write({'active': False})
```

When restoring a `refuse` leave in Odoo 19 via ORM:
- Note that `action_reset_confirm()` was removed in Odoo 19 and `action_back_to_approval()` only applies when `state == 'validate'`. Under `sudo()`, `leaves.sudo().action_approve()` directly validates refused leaves and recreates `resource.calendar.leaves` and `hr.work.entry` records cleanly.

## ⚠️ Pitfalls

- **Never create test `hr.work.entry` records directly with `'state': 'validated'`:** `HrWorkEntry.create()` unconditionally calls `_check_if_error()` → `_mark_already_validated_days()`, which sees the newly inserted `'validated'` row itself and immediately flips it to `'conflict'`. Create in `'draft'` and call `action_validate()`.
- **Never call `generate_work_entries(d_from, d_to, force=True)` across `state='validated'` dates:** Core `HrVersion._generate_work_entries(force=True)` keeps existing `validated` entries but still generates new `8h` entries on those same dates, causing `_mark_already_validated_days()` to mark them `state='conflict'`. Split around `validated` dates first.
- **Detach `leave_id` on archived work entries (`_work_entry_fields_to_nullify`):** Core `hr_work_entry_holidays` omits `'leave_id'` from `_work_entry_fields_to_nullify()`; repeated `force=True` runs otherwise accumulate archived copies with `leave_id` set, causing `HrLeave._regen_work_entries()` under `active_test=False` to exceed 24h and crash with `ValidationError`.
- **Include undefined-type entries in pre-regeneration cleanup:** Before calling `version.generate_work_entries(d_from, d_to, force=True)`, also safely archive any uncancelled `work_entry_type_id = False` rows so core `force=True` nullification does not archive them without `hr_work_entry_no_check=True`.

## Verification

```bash
/Users/gamal/.pyenv/versions/3.11.9/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf \
  -d solargy \
  --test-enable \
  --test-tags :TestLeaveWorkEntryConflict \
  --stop-after-init \
  --http-port=8029
```

## References

- Related file: `orm/hr-payroll-odoo19-midperiod-renewal-work-entry-gaps-and-worked-leaves-singleton.md`
- Implementation: `solargy_hr/models/hr_payslip.py`, `solargy_hr/tests/test_leave_work_entry_conflict.py`
