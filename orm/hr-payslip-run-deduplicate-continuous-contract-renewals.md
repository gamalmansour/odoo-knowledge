# Odoo 19 `hr.payslip.run` Generates Duplicate Full-Month Payslips on Mid-Period Contract Renewals

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19                                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.payslip.run`, `hr.version`, `duplicate payslip`, `_get_valid_version_ids`, `contract renewal`, `hr_payroll`

---

## Problem

When an employee's annual contract is renewed mid-payroll-period using **New Contract** (`hr.version`, e.g., Contract 1 ends `2026-11-09` and Contract 2 starts `2026-11-10` with the same salary inside a Pay Run spanning `2026-10-25 → 2026-11-21`), Odoo 19's `hr.payslip.run._get_valid_version_ids()` returns **both** contract versions and generates **two separate payslips** for the same employee in the same Pay Run.

If `hr.payslip` aggregates continuous overlapping versions (to avoid false `OUT` days) or fixes monthly `BASIC = version.wage`, **both payslips compute 100% of the monthly salary**, risking a **2x salary payout** if HR validates the batch without deleting the superseded slip.

## Root Cause

In `enterprise/hr_payroll/models/hr_payslip_run.py`, `_get_valid_version_ids()` iterates through all versions matching `[date_start, date_end]` and adds a version whenever `contract_date_start` changes between versions — even when the two contracts are back-to-back with zero gap (`prev.contract_date_end + 1 day == next.contract_date_start`) and carry identical structure and compensation.

## Solution ✅

Override `HrPayslipRun._get_valid_version_ids()` to deduplicate continuous zero-gap versions per employee that share identical `structure_type_id`, `wage_type`, and monthly compensation, keeping only the latest active version in the period (while still keeping both versions whenever there is a genuine employment gap or a salary/structure change):

```python
class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def _get_valid_version_ids(self, date_start=None, date_end=None, structure_id=None,
                               company_id=None, employee_ids=None, schedule_pay=None):
        version_ids = super()._get_valid_version_ids(
            date_start=date_start, date_end=date_end, structure_id=structure_id,
            company_id=company_id, employee_ids=employee_ids, schedule_pay=schedule_pay,
        )
        if not version_ids or len(version_ids) < 2:
            return version_ids
        versions = self.env['hr.version'].sudo().browse(version_ids)
        by_emp = {}
        for ver in versions:
            by_emp.setdefault(ver.employee_id.id, []).append(ver)
        superseded_ids = set()
        for emp_vers in by_emp.values():
            if len(emp_vers) < 2:
                continue
            ordered = sorted(emp_vers, key=lambda v: (v.contract_date_start or v.date_version or date.min, v.id))
            for idx in range(len(ordered) - 1):
                prev_v, next_v = ordered[idx], ordered[idx + 1]
                prev_end = prev_v.contract_date_end
                next_start = next_v.contract_date_start or next_v.date_version
                is_continuous = not prev_end or (next_start and prev_end + timedelta(days=1) >= next_start)
                if is_continuous and self._solargy_version_comp_key(prev_v) == self._solargy_version_comp_key(next_v):
                    superseded_ids.add(prev_v.id)
        return [vid for vid in version_ids if vid not in superseded_ids]
```

## ⚠️ Pitfalls

- **Never deduplicate when salary or structure changed:** Comparing `(structure_type_id, wage_type, wage, housing, transportation, other)` ensures genuine mid-month raises or structure changes still produce separate split slips when needed.
- **Check `action_payslip_cancel()` on duplicate cleanup:** When HR cancels an existing duplicate slip in an open Pay Run, make sure custom `action_payslip_cancel()` overrides do NOT overwrite `state = 'waived'` penalties back to `'confirmed'`.

## Verification

1. Create two back-to-back `hr.version` records (`2025-11-10..2026-11-09` and `2026-11-10..2027-11-09`) with the same wage and structure type.
2. Call `run._get_valid_version_ids(employee_ids=[emp.id])` for `2026-10-25..2026-11-21` → assert only `[v2.id]` is returned.
3. Change `v2.wage` to a different value and re-call → assert `{v1.id, v2.id}` are both returned.

## References

- Core Pay Run version selection: `enterprise/hr_payroll/models/hr_payslip_run.py` (`_get_valid_version_ids`)
