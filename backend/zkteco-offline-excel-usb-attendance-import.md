# ZKTeco Offline USB Excel & DAT Attendance Import with Auto-Linking and Open-Session Safety

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `zkteco`, `biometric`, `excel-import`, `usb-attendance`, `hr_attendance`, `openpyxl`, `xlrd`, `auto-linking`, `odoo19`

---

## Problem

In many real-world client deployments, biometric attendance machines (such as ZKTeco MB20, K40, or uFace series) are installed in **Standalone** mode without active ADMS / Push firmware, or company security policies forbid connecting the biometric terminal to the internet or corporate WAN.

In this offline scenario, HR officers download attendance records via USB flash drive directly from the machine's menu. This generates an `.xls`, `.xlsx`, `.csv`, or `.dat` file containing hundreds or thousands of raw punch records.

Attempting to import this data into standard Odoo Attendance (`hr.attendance`) fails due to multiple technical roadblocks:
1. **Blocking Open-Session Constraint (`_check_validity`):**
   ```text
   odoo.exceptions.ValidationError: Cannot create new attendance record for Employee X, the employee hasn't checked out since Y.
   ```
   If an employee forgot to punch out on a prior day, Odoo's core SQL/Python constraint blocks creating *any* future attendance records for that employee until the historical record is manually closed.
2. **Proprietary ZKTeco File Layouts:**
   Exported Excel files from ZKTeco terminals often have non-standard layouts with metadata headers, differing column labels (`AC-No.`, `No.`, `Name`, `Time`, `State`), and localized 12-hour timestamps (e.g. `01-Sep-26 08:30 AM`).
3. **Unmapped Biometric IDs:**
   Employees created in Odoo rarely have their `biometric_id` populated in advance, causing 100% of imported punches to be orphaned or rejected.
4. **Door Access Double-Punching:**
   When terminals control door locks, employees punch 5–10 times a day to pass doors. Standard imports create overlapping or broken attendance pairs.

---

## Root Cause

1. **Odoo 19 Attendance Validation:**
   Core Odoo enforces that for any employee, an open attendance session (`check_out = False`) cannot be followed by another `check_in`. When bulk-importing multi-day attendance files, the first missed check-out crashes the entire transaction.
2. **Tabular File Variability:**
   Different ZKTeco firmware versions export either legacy binary `.xls` (BIFF8 format), modern `.xlsx` (ZIP XML), or delimited `.dat`/`.csv` text files. A robust solution must dynamically support all four formats and automatically detect the column indices regardless of header position.
3. **Name Discrepancies:**
   Machine names often contain minor spelling variations (e.g. Arabic Alif with or without Hamza `أ/ا/إ`, Ta Marbuta vs Ha `ة/ه`, extra spaces).

---

## Solution ✅

Implement a dedicated TransientModel import wizard (`zkteco.attendance.import.wizard`) with automated column discovery, name normalization, in-memory caching, and defensive session auto-closure:

### 1. In-Memory Lookup Caching & Batch Pre-fetching

Avoid N+1 queries during imports of 2,000+ rows by pre-loading employees into dictionary caches:

```python
# Cache by biometric ID and normalized names
emp_by_pin = {}
emp_by_name = {}
for emp in self.env['hr.employee'].search([('company_id', '=', self.company_id.id)]):
    if emp.biometric_id:
        emp_by_pin[str(emp.biometric_id).strip()] = emp
    norm_name = self._normalize_name(emp.name)
    if norm_name:
        emp_by_name[norm_name] = emp
```

### 2. Smart Arabic & English Name Normalization

Auto-link employees if their `biometric_id` is blank by matching sanitized names:

```python
@api.model
def _normalize_name(self, name: str) -> str:
    if not name:
        return ''
    text = str(name).strip().lower()
    # Normalize Arabic characters
    text = re.sub(r'[أإآا]', 'ا', text)
    text = re.sub(r'[ة]', 'ه', text)
    text = re.sub(r'[يى]', 'ي', text)
    # Remove special characters and collapse spaces
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split())
```

### 3. Defensive Open-Session Auto-Closure (`models/zkteco_attendance_log.py`)

When creating a new day's attendance, detect and auto-close any unclosed sessions from earlier days to satisfy Odoo's `_check_validity()` constraint cleanly:

```python
# Auto-close prior unclosed attendance records from earlier days
open_prior_attendances = Attendance.search([
    ('employee_id', '=', employee.id),
    ('check_out', '=', False),
    ('check_in', '<', start_utc),
])
for prior in open_prior_attendances:
    prior.write({
        'check_out': prior.check_in,
        'out_mode': 'biometric',
    })

# Now safe to create new Check-In without ValidationError
new_att = Attendance.create({
    'employee_id': employee.id,
    'check_in': self.punch_time,
    'in_mode': 'biometric',
    'zk_device_id': self.device_id.id,
})
```

### 4. Chronological Sorting & 60-Second Debounce

Sort all parsed rows chronologically `(pin, punch_datetime)` before evaluation. Skip any punches that occur within 60 seconds of the previous punch for the same employee to eliminate sensor bouncing.

---

## ⚠️ Pitfalls

1. **xlrd vs openpyxl:**
   ZKTeco `.xls` exports are binary BIFF8 files which openpyxl cannot read (`InvalidFileException`). You MUST use `xlrd` for `.xls` and `openpyxl` for `.xlsx`.
2. **Never Let Open Sessions Crash Batch Imports:**
   If a single employee has an open attendance from 3 days ago, standard `Attendance.create()` will raise a `ValidationError` and roll back the *entire* import of 2,000 punches. Always auto-close prior open sessions or wrap the record creation in a safe savepoint.
3. **Locale Timestamp Parsing:**
   ZKTeco formats timestamps with short month names like `01-Sep-26 08:30 AM`. Use `%d-%b-%y %I:%M %p` with fallback parsing for `%Y-%m-%d %H:%M:%S` and ISO 8601.
4. **Always Provide Raw Logs:**
   Never write directly to `hr.attendance` without saving the raw punches in a staging table (`zkteco.attendance.log`). Staging logs allow HR to audit original timestamps and reprocess unmapped employees once their profile is linked.

---

## Verification

1. Run unit test suite:
   ```bash
   odoo-bin -c odoo.conf -d solargy -u solargy_zkteco_attendance --test-tags=solargy_zkteco_attendance --stop-after-init
   ```
2. Import a real ZKTeco MB20 `.xls` file with 2,000+ rows via **Attendances > Import Attendance File**.
3. Verify that all punches are ingested into `zkteco.attendance.log`, unmapped employees are auto-linked, and daily attendances in `hr.attendance` reflect accurate First-In / Last-Out hours without validation errors.
