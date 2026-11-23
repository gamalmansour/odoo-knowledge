# `check_company=True` on Many2one Driving a `related` `company_id` Causes Empty Dropdown on Unsaved Forms

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `check_company`, `many2one`, `related`, `company_id`, `empty-dropdown`, `ui-form`

---

## Problem

> When creating a new record in the Odoo UI (before saving), clicking on the `employee_id` (or other primary Many2one) dropdown displays **zero existing records** — showing only `"Create..."` — even though valid records exist in the active company and unit tests pass when passing `employee_id` directly in `.create({...})`.

```text
# Server log shows web_name_search returns 0 records and clicking the only dropdown option opens the Create modal:
POST /web/dataset/call_kw/hr.employee/web_name_search HTTP/1.1 200
POST /web/dataset/call_kw/hr.employee/get_views HTTP/1.1 200
```

## Root Cause

> When a model declares `company_id` as a `related` field derived from `employee_id.company_id` AND also sets `check_company=True` on `employee_id`:
>
> ```python
> employee_id = fields.Many2one('hr.employee', required=True, check_company=True)
> company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=True)
> ```
>
> On an unsaved new form (`NewId`), `employee_id` is empty so `company_id` evaluates to `False`. Odoo's `check_company=True` auto-domain compiles to `[('company_id', 'in', [company_id, False])]`, which evaluates to `[('company_id', 'in', [False])]` — filtering out every company-owned employee record!

## Solution ✅

> Remove `check_company=True` from the Many2one field that **defines** the record's `company_id` via `related=`. Keep `check_company=True` only on *secondary* Many2one fields (e.g., `department_id`, `branch_id`, `journal_id`) or when `company_id` has an explicit `default=lambda self: self.env.company`.

```python
# ✅ Correct: employee_id defines company_id via related=, and multi-company ir.rule filters hr.employee
employee_id = fields.Many2one(
    'hr.employee',
    string='Employee',
    required=True,
    ondelete='restrict',
    index=True,
)
company_id = fields.Many2one(
    'res.company',
    related='employee_id.company_id',
    store=True,
    readonly=True,
    index=True,
)
```

## ⚠️ Pitfalls

- **Unit Tests Hide This Bug:** Calling `Model.create({'employee_id': emp.id})` in Python tests bypasses the web client's `web_name_search` auto-domain, so all unit tests pass while the live UI dropdown is completely broken! Always run a Playwright / UI smoke test on brand-new unsaved forms.
- **Alternative When `company_id` Is Independent:** If the model has an editable/defaulted `company_id = fields.Many2one('res.company', default=lambda self: self.env.company)` (not `related='employee_id.company_id'`), keeping `check_company=True` on `employee_id` works properly because `company_id` is pre-populated on `default_get`.

## Verification

```bash
# Open a New form in Playwright/browser, click employee_id dropdown, confirm active-company employees populate immediately.
```

## References

- Discovered via live Playwright E2E UI verification on `eg_hr_operations` (`hr.employee.clearance`) on Odoo 19.0 Enterprise.
