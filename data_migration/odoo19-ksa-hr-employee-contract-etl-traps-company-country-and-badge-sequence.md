# Odoo 19 KSA HR & Payroll ETL Migration Traps: Hidden Country Structure Types, Badge Sequence Overwrite, & `bank_account_ids` M2M

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | data_migration                             |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hr.employee`, `hr.version`, `l10n_sa_hr_payroll`, `hr.payroll.structure.type`, `bank_account_ids`, `iban`, `data_migration`, `odoo19`

---

## Problem

> When migrating legacy Saudi HR & Payroll master sheets into a freshly provisioned Odoo 19 database (where `l10n_sa_hr_payroll` is installed, `hr.contract` has been unified into `hr.version`, and custom KSA HR addons are active), three silent or blocking ETL traps occur:
> 1. Querying `hr.payroll.structure.type` via XML-RPC/JSON-RPC returns only generic `Employee` (`US` / `False`) — `KSA Employee` (`Saudi Arabia: Monthly Pay`) appears completely missing even though `l10n_sa_hr_payroll` is `installed`.
> 2. Passing legacy employee codes (`1001..3373`) into `hr.employee.create()` together with `country_id` silently overwrites the legacy code with auto-generated sequences (`SA-0001` / `NS-0001`).
> 3. Writing `bank_account_id` fails on Odoo 19 (`Invalid field 'bank_account_id' on model 'hr.employee'`), and naive numeric-only Saudi IBAN regexes (`^SA\d{22}$`) reject valid SAMA corporate/branch IBANs containing letters (e.g. Banque Saudi Fransi `SA82550000000M0623000143`).

```text
ValueError: Invalid field 'bank_account_id' on model 'hr.employee'
ValidationError: رقم الايبان يجب ان يكون من 24 رقم
ValidationError: رقم الهوية يجب ان يكون 10 ارقام
```

## Root Cause

1. **Country Record Rule Hiding KSA Payroll Structures:** Fresh Odoo.sh / SaaS databases initialize `res.company` (`id=1`) with `country_id = United States` and `currency_id = USD`. Standard payroll record rules filter `hr.payroll.structure.type` and `hr.payroll.structure` by `['|', ('country_id', '=', False), ('country_id', 'in', company_ids.country_id.ids)]`. Even for `admin` (`uid=2`), `search_read([])` hides `KSA Employee` until the company's `country_id` is switched to `Saudi Arabia`.
2. **`create()` Sequence Hook Overwriting Legacy Codes:** KSA customization modules commonly override `hr.employee.create()` to call `_assign_badge_number(vals)` whenever `country_id` is present, unconditionally overwriting `vals['employee_number']` (while `write()` does not).
3. **Odoo 19 `hr.version` & Multi-Bank Schema + ISO-13616 Alphanumeric IBANs:**
   - Odoo 19 replaced single `bank_account_id` on `hr.employee` (and `hr.contract`) with Many2many `bank_account_ids` on `hr.employee` and `hr.version` (supporting salary split allocations).
   - Under ISO-13616 / SAMA rules, Saudi IBANs are 24 characters starting with `SA` + 2 check digits + 2-digit SAMA bank code + 18 alphanumeric characters (`^SA\d{2}[A-Z0-9]{20}$`), validated via Mod-97 (`int(rearranged_numeric) % 97 == 1`), NOT digits-only.

## Solution ✅

1. **Stage 1 Foundation First (Before Discovering Structure Types):**
   Activate `SAR`, set `res.company` (`id=1`) `country_id` to `SA` (`base.sa`) and `currency_id` to `SAR`, and exclude the system `Administrator` employee (`id=1`) from Saudization/Nitaqat KPIs (`counts_for_saudization=False`). Immediately re-query `hr.payroll.structure.type` — `KSA Employee` (`default_struct_id = Saudi Arabia: Monthly Pay`) becomes visible.
2. **Preserve Legacy Employee Codes Across `create()` + `write()`:**
   After `emp_id = execute_kw('hr.employee', 'create', [vals])`, immediately execute `write([emp_id], {'employee_number': code_str, 'barcode': code_str, 'pin': code_str})` (plus any custom biometric fields like `emp_code` / `device_id`) so `create()` hooks cannot clobber the legacy code.
3. **Validate Saudi IBANs via ISO-13616 Mod-97 & Link `bank_account_ids` via Command `(6, 0, [id])`:**

```python
import re

def is_valid_sa_iban(raw: str) -> tuple[bool, str]:
    cleaned = re.sub(r"\s+", "", (raw or "").strip().lstrip("'")).upper()
    if len(cleaned) != 24 or not re.match(r"^SA\d{2}[A-Z0-9]{20}$", cleaned):
        return False, cleaned
    rearranged = cleaned[4:] + cleaned[:4]
    numeric = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    return int(numeric) % 97 == 1, cleaned

# Link res.partner.bank to Odoo 19 hr.employee (propagates to current_version_id):
models.execute_kw(db, uid, pwd, "hr.employee", "write", [[emp_id], {
    "bank_account_ids": [(6, 0, [partner_bank_id])],
}])
```

4. **Two-Pass Manager (`parent_id`) Linking + Archived Stubs for Out-of-Sheet Managers:**
   Import all employees with `parent_id=False` in Pass 1; create archived (`active=False`, `counts_for_saudization=False`) stub `hr.employee` records for legacy managers absent from the active headcount sheet; link `parent_id` for all subordinates in Pass 2.

## ⚠️ Pitfalls

- **Never stuff non-24-char local account numbers into custom `bank_iban_number` fields** guarded by `@api.constrains`: keep custom `bank_iban_number` strictly for verified 24-char unique Saudi IBANs, store local account numbers in `res.partner.bank.acc_number`, and log malformed/duplicate accounts in the employee Chatter + client exception workbook.
- **Hijri text dates in Gregorian Excel columns** (e.g. `'10/06/1405'`): detect years `1300..1500` and convert deterministically instead of dropping `birthday`.
- **Unmapped GOSI vs Basic Wage:** In legacy Saudi HR exports without allowance breakdowns, `GOSI Subject Salary` frequently differs from `Basic Salary` (because GOSI = Basic + Housing, or capped/frozen). Map Basic to `hr.version.wage` and GOSI base to `gosi_salary` without fabricating allowances.

## Verification

```python
# Confirm KSA Structure Type is unlocked and assigned across all active employees:
versions = models.execute_kw(
    db, uid, pwd, "hr.version", "search_read",
    [[["employee_id.active", "=", True]]],
    {"fields": ["employee_id", "wage", "structure_type_id", "contract_date_start"]}
)
assert all(v["structure_type_id"] and "KSA" in v["structure_type_id"][1] for v in versions)
```

## References

- Related file: `orm/odoo19-hr-version-payroll-contract-lifecycle.md`
- Related file: `data_migration/excel-import-header-mapping-and-many2one-resolution.md`
