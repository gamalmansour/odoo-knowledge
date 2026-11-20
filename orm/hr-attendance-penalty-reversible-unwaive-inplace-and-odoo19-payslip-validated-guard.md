# HR Attendance Penalty Reversible Unwaive (In-Place Update, Preserved Uncovered Minutes, and Odoo 19 `validated` Payslip Guard)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19 (principles apply to 17, 18, 19)        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-11-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.attendance`, `hr.attendance.penalty`, `hr.absence`, `hr.payslip`, `unwaive`, `MissingError`, `validated`, `acl`, `odoo19`

---

## Problem

When HR mistakenly waives an attendance or absence penalty (`action_waive()` / `hr.absence.action_justify()`) and needs to reverse it ("Unwaive Penalty"):

1. **Lost Delay Data on Recalc:** Attendance penalty re-evaluation overwrote `'uncovered_minutes': 0` on existing `waived` penalties, permanently erasing the original uncovered delay minutes.
2. **`MissingError` & Lost Chatter on Form View:** Re-evaluating `hr.attendance` by unlinking `non_waived_pen` and creating a new penalty deletes the open record (`rec.id`) mid-click when `action_unwaive()` transitions `waived -> draft`, crashing the Web Form View with `MissingError` and destroying Chatter audit history.
3. **Self-Counting Against the `1.00`-Day Cap:** Once an attendance penalty is updated in-place (`target_pen`) instead of unlinked first, any same-day ceiling query (`other_day_pens = Penalty.search(...)`) that does not exclude `('id', '!=', target_pen.id)` counts `target_pen` against its own `1.00`-day cap, halving or zeroing `early_out` penalties.
4. **Odoo 19 `hr.payslip.state` Trap (`'validated'` vs `'done'`):** In Odoo 19 Enterprise (`hr_payroll`), `hr.payslip.action_payslip_done()` sets `state = 'validated'` (NOT `'done'` as in Odoo 17/18). Guards checking only `payslip_id.state in ('done', 'paid')` silently miss confirmed Odoo 19 payslips!
5. **Attendance Manager `AccessError`:** Exposing `Unwaive Penalty` / `Reset to Unjustified` buttons and server actions to `hr_attendance.group_hr_attendance_manager` crashes with `AccessError` if `ir.model.access.csv` restricts write/create to `hr.group_hr_manager`, OR if the payslip guard reads `rec.payslip_id.state` without `.sudo()` for an Attendance Manager lacking Payroll rights.

## Root Cause

- `_evaluate_late_check_in()` / `_evaluate_early_check_out()` hardcoded `'uncovered_minutes': 0` on `waived_pen` and unconditionally called `non_waived_pen.unlink()` before recreating records.
- `hr.payslip` state selection in Odoo 19 Enterprise is `('draft', 'validated', 'paid', 'cancel')` (with `'validated'` displayed as `'Done'` via `state_display`), whereas legacy code checked `'done'`.
- Same-day sibling attendance scans using `target_date - 1 .. target_date + 2` UTC bounds without filtering by each attendance's local calendar date could unintentionally re-evaluate adjacent days.

## Solution ✅

### 1. Preserve `uncovered_minutes` & Support In-Place Updates via `solargy_preserve_penalty_id`

```python
preserve_id = self.env.context.get('solargy_preserve_penalty_id')
target_pen = (
    non_waived_pen.filtered(lambda p: p.id == preserve_id)[:1]
    if preserve_id
    else Penalty
)
if not target_pen and len(non_waived_pen) == 1:
    target_pen = non_waived_pen
extra_non_waived = non_waived_pen - target_pen
if extra_non_waived:
    extra_non_waived.unlink()

# Never zero uncovered_minutes on waived penalties:
if waived_pen:
    waived_pen.write({
        ...,
        'uncovered_minutes': uncovered,
    })
    return

# Exclude target_pen from same-day cap search so it never caps itself:
other_domain = [
    ('employee_id', '=', self.employee_id.id),
    ('date', '=', local_date),
    ('penalty_type', 'in', ['late_in', 'early_out']),
    ('state', '!=', 'waived'),
]
if target_pen:
    other_domain.append(('id', '!=', target_pen.id))
```

On every early exit (`total_delay <= 0`, `uncovered <= 0`, `ded_days <= 0.0`, or `check_out == False`), if `preserve_id and target_pen.id == preserve_id`, update `target_pen` in-place to `deduction_days = 0.0` instead of unlinking it so the open Form View never hits `MissingError`.

### 2. Guard Against Odoo 19 `'validated'` / `'done'` / `'paid'` Payslips with `.sudo()`

```python
for rec in self:
    slip = rec.sudo().payslip_id
    if rec.state == 'applied' or (slip and slip.state in ('validated', 'done', 'paid')):
        raise UserError(
            _("Cannot unwaive a penalty linked to a validated payslip (%s).", rec.name)
        )
```

### 3. Reversible `action_unwaive()` + Legacy Zeroed Recovery + Local-Date Sibling Filter

- Recover legacy zeroed records in `_recalculate_tier_penalty()` via:
  ```python
  unc = self.uncovered_minutes or max(0, (self.total_delay_minutes or 0) - (self.covered_by_allowance or 0))
  if unc > 0 and self.uncovered_minutes != unc:
      self.uncovered_minutes = unc
  ```
- Revert linked `justified` `hr.absence` records back to `unjustified` using `company.absence_unjustified_deduction_days or 2.0`.
- Re-evaluate `rec.attendance_id` in-place with `with_context(solargy_preserve_penalty_id=rec.id)` and filter same-day sibling attendances strictly by `sib._get_local_attendance_date() == target_date`.
- Post a Chatter audit message on the preserved `rec.id` and refresh overlapping `draft`/`verify` payslips while skipping slips where `_has_orphan_salary_line()` is `True`.
- Grant `hr_attendance.group_hr_attendance_manager` `1,1,1,0` ACLs on `hr.attendance.penalty` and `hr.absence` in `ir.model.access.csv` to match the view buttons and bulk `ir.actions.server` (`group_ids`).

## ⚠️ Pitfalls

- **Never check only `slip.state in ('done', 'paid')` in Odoo 19:** Always include `'validated'` (`('validated', 'done', 'paid')`), because `hr.payslip.action_payslip_done()` writes `'validated'` in Odoo 19.
- **Never read `rec.payslip_id.state` without `.sudo()` inside attendance-manager actions:** Users with `hr_attendance.group_hr_attendance_manager` rarely hold Payroll ACLs and will hit `AccessError` on `hr.payslip`.
- **Never forget `('id', '!=', target_pen.id)` when converting unlink-then-create into in-place writes:** Without it, `target_pen` counts against its own daily cap.
- **Never re-evaluate all attendances in a `target_date - 1 .. target_date + 2` UTC window without checking local date:** Otherwise waiving/unwaiving Day N can mutate penalties on Day N-1 or Day N+1.

## Verification

```bash
/Users/gamal/.pyenv/versions/3.11.9/bin/python3 /Users/gamal/odoo/odoo19.0/odoo-bin \
  -c /Users/gamal/odoo/odoo19.0/solargy.conf \
  -d solargy_test_p6 \
  --data-dir=/tmp/solargy_test_p6_data \
  -u solargy_hr \
  --test-enable \
  --test-tags /solargy_hr \
  --stop-after-init \
  --http-port=8029
```

## References

- Related file: `orm/hr-attendance-penalty-dual-mission-audit-notes-and-session-cap.md`
- Related file: `Best Practices/out-of-order-retroactive-event-convergence-and-live-config-audit.md`
