# Out-of-Order (Retroactive) Event Convergence, Live Master-Data Inspection, and Cross-Table Invariant Audits in Odoo ERP

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | All (15, 16, 17, 18, 19, 20)               |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `best-practices`, `pre-mortem`, `e2e-testing`, `retroactive`, `idempotency`, `commutativity`, `hr.leave`, `hr.absence`, `hr.attendance`, `hr.payslip`, `audit`

---

## Problem

Even when a custom Odoo module has unit tests, E2E tests, and a 6-month pre-mortem risk analysis, two classes of production bugs still slip through during real-world payroll/financial closing:

1. **The "Happy Chronology" Trap (Out-of-Order / Retroactive Operations):**
   - In E2E tests, developers naturally test events in chronological order:
     `Employee requests Leave on Sep 29 -> HR approves Leave on Sep 29 -> Nightly Absence Cron runs on Oct 1 -> Payslip computed on Oct 25`.
   - In real production, events happen **out of order (retroactively)**:
     1. Employee is absent on `Sep 30` without submitting a leave request yet.
     2. Nightly Absence Cron runs on `Oct 1` and creates `hr.absence` (`state = 'unjustified'`) + a `2x` `hr.attendance.penalty` (`2,000 EGP`).
     3. Draft Payslip is generated on `Oct 20` pulling the `2,000 EGP` deduction.
     4. On `Oct 25` (24 days later, during payroll review), the employee submits a `Casual Leave` for `Sep 30` and HR approves it retroactively.
   - Because `hr.leave.write()` only re-evaluated `hr.attendance` punches (lateness/early departure) and did not reconcile existing `hr.absence` records or refresh open `Draft` payslips, the `2,000 EGP` unjustified absence penalty remained stuck on the employee's payslip despite having an `APPROVED` leave!

2. **The "Assumed Master-Data Configuration" Trap:**
   - To exclude short 15-minute morning lateness permissions (`Excuses`) from clearing full-day absences, the developer filtered `hr.leave` with `('request_unit_hours', '=', False)`, assuming that all full-day leaves and external missions were configured in `Days` (`request_unit = 'day'`).
   - In production, HR had configured the **`Missions`** time-off type (`hr.leave.type`) with `Take Time Off in = Hours` (`request_unit = 'hour'`, `request_unit_hours = True`) so employees could log either 3-hour missions or full 8-hour missions.
   - As a result, `('request_unit_hours', '=', False)` silently ignored all `Missions` (`8:00 hours`), penalizing employees on approved external missions with `2x` unjustified absence deductions.

---

## Root Cause

1. **Lack of Commutativity (Order-Independence) Between Coupled State Machines:**
   When Model A (`hr.leave`, `resource.calendar.leaves`, `hr.version`) and Model B (`hr.absence`, `hr.attendance.penalty`, `hr.payslip`) depend on each other, writing synchronization logic only inside Model B's batch generator (`_detect_and_create_absences` / `compute_sheet`) makes the system **order-dependent**. If Model A is mutated *after* Model B has already materialized records, Model B stays stale.
2. **Writing Domain Filters Against Assumed Config Instead of Live Master Data:**
   Filtering on a technical implementation field (`request_unit_hours = False`) as a proxy for a business concept ("not a short lateness excuse") breaks whenever administrators configure another business concept (`Missions`, `Unpaid`) using hourly units.
3. **E2E Tests Without Cross-Table Invariant Queries on Live Data:**
   Unit tests run against synthetic `setUpClass` records that mirror the developer's assumptions rather than the client's actual master data and historical transaction order.

---

## Solution ✅

### 1. Enforce Bidirectional / Commutative Convergence (`A -> B == B -> A`)

For every coupled workflow (Leaves, Missions, Public Holidays, Biometric Punches, Contract Schedule Changes, Absences, Penalties, Draft Payslips), the final database state MUST be identical regardless of the order in which events occur:

```python
# ✅ Always test and implement BOTH chronological orders:
# Order 1 (Forward):   Approve Leave -> Run Absence Cron -> Compute Draft Payslip
# Order 2 (Retroactive): Run Absence Cron -> Compute Draft Payslip -> Retroactively Approve Leave
# Both MUST converge to: absence.state == 'leave', penalty unlinked, draft payslip updated!
```

Hook `create()`, `write()`, and `unlink()` on the upstream model (`hr.leave`, `resource.calendar.leaves`, `hr.version`) to actively reconcile downstream records (`hr.attendance`, `hr.absence`, `hr.attendance.penalty`) and refresh open `Draft` / `Verify` payslips (`_refresh_draft_payslip_sheets()`).

### 2. Inspect Live Master Data Before Writing Domain Filters

Before filtering on any configuration model (`hr.leave.type`, `hr.salary.rule`, `account.journal`, `stock.picking.type`), always query the live table first:

```sql
SELECT id, name->>'en_US' AS name, request_unit, time_type, unpaid
FROM hr_leave_type
WHERE active = true;
```

Encapsulate business classification in an explicit helper method (`_is_absence_covering_leave()`) that checks `time_type == 'other'`, mission keywords, and duration thresholds rather than relying on a blind `('request_unit_hours', '=', False)` domain.

### 3. Guard Future Dates During Retroactive Refusal / Deletion

When a leave is refused or deleted (`state` transitions from `leave` back to `unjustified`), never flag future dates (`abs_rec.date >= today`) as `unjustified` absences, and always verify whether an `hr.attendance` punch exists on that date before restoring an unjustified absence penalty.

### 4. Mandatory Cross-Table SQL Invariant Audit Before Sign-off

Before declaring any HR/Payroll/Accounting fix complete on a client database, execute cross-table invariant queries that assert **zero contradictions** across coupled tables:

```sql
-- Invariant 1: Zero unjustified absences on days where the employee punched in
SELECT a.id, a.date, a.employee_id
FROM hr_absence a
JOIN hr_attendance att ON att.employee_id = a.employee_id
  AND (att.check_in AT TIME ZONE 'UTC' AT TIME ZONE 'Africa/Cairo')::date = a.date
WHERE a.state = 'unjustified';

-- Invariant 2: Zero unjustified_absence penalties on days covered by an approved Leave or Mission
SELECT p.id, p.date, p.employee_id, lt.name->>'en_US'
FROM hr_attendance_penalty p
JOIN hr_leave l ON l.employee_id = p.employee_id
  AND l.state = 'validate'
  AND p.date BETWEEN l.request_date_from AND l.request_date_to
JOIN hr_leave_type lt ON lt.id = l.holiday_status_id
WHERE p.penalty_type = 'unjustified_absence' AND p.state != 'applied';

-- Invariant 3: Zero drift between Draft Payslip input lines and active penalties in the period
SELECT p.id AS slip_id, p.employee_id
FROM hr_payslip p
WHERE p.state IN ('draft', 'verify')
  AND ABS(
    COALESCE((SELECT SUM(il.amount) FROM hr_payslip_input il JOIN hr_payslip_input_type it ON it.id = il.input_type_id WHERE il.payslip_id = p.id AND it.code = 'UNJ_ABS_DED'), 0) -
    COALESCE((SELECT SUM(pen.deduction_amount) FROM hr_attendance_penalty pen WHERE pen.employee_id = p.employee_id AND pen.date BETWEEN p.date_from AND p.date_to AND pen.penalty_type = 'unjustified_absence' AND pen.state IN ('draft', 'confirmed')), 0)
  ) > 0.05;
```

---

## ⚠️ Pitfalls

- **Never assume `create()` always starts in `draft`:** HR managers, imports, or single-step approval flows can create `hr.leave` records directly in `state == 'validate'`. Always trigger downstream synchronization in `create()`, `write()`, AND `unlink()`.
- **Never touch `state == 'applied'` penalties on closed payslips:** Retroactive cleanup hooks must strictly filter `p.state != 'applied'` so historical closed/paid payslips remain immutable.
- **Never blame "the previous developer" before checking `git blame`:** Own every line of the codebase, audit live data invariants first, and verify both forward and retroactive event sequences in every test suite.

---

## References

- Related file: `performance/batch-absence-detection-across-working-calendars.md`
- Related file: `orm/sliding-flexible-checkin-window-vs-native-flexible-hours.md`
