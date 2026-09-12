# hr.leave.employee_ids removed in Odoo 18 — and the naive rename introduces a singleton crash

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `migration`, `hr_holidays`, `hr.leave`, `employee_ids`, `employee_id`, `ensure_one`, `mapped`, `Many2one`

---

## Problem

Any code or view reading `hr.leave.employee_ids` raises on Odoo 18:

```
AttributeError: 'hr.leave' object has no attribute 'employee_ids'
```

Then, after the obvious fix (`employee_ids` → `employee_id`), a *different* crash
appears in exactly the places the first one was:

```
ValueError: Expected singleton: hr.leave(24, 23)
```

## Root Cause

**Odoo ≤17** carried `employee_ids = fields.Many2many('hr.employee')` on `hr.leave`
(`addons/hr_holidays/models/hr_leave.py:205` in 17.0) so one request could cover
several employees. **Odoo 18 deleted it.** The only surviving `employee_ids` in
`hr_leave.py` is a local variable inside a create-values helper — not a field.

The second crash is the trap. `employee_ids` was a Many2many, and x2many fields
override `Field.__get__` to allow access on a multi-record recordset (returning the
union). `employee_id` is a **Many2one**, which goes through the base
`Field.__get__` — and that calls `record.ensure_one()`
(`odoo/fields.py:1227`, the `# only a single record may be accessed` branch).

So `leaves.employee_ids` was legal on a recordset of many leaves; `leaves.employee_id`
is not. A search-and-replace migration turns a clean AttributeError into a
ValueError that only fires when the recordset happens to hold more than one row —
typically a report printed from a list view, never in a single-record test.

## Solution ✅

Three distinct rewrites, decided by what the old code was doing:

```python
# 1) Iterating the employees of ONE leave  ->  iterate the Many2one (0 or 1 rows)
for emp in rec.employee_ids:          # BEFORE
for emp in rec.employee_id:           # AFTER  (safe: empty M2o iterates zero times)

# 2) The "only makes sense for a single employee" guard  ->  "is there one at all"
if len(rec.employee_ids) == 1:        # BEFORE
if rec.employee_id:                   # AFTER

# 3) Collecting employees across a MULTI-record recordset  ->  mapped(), never .employee_id
for line in leaves.employee_ids:            # BEFORE (legal on many leaves)
for line in leaves.mapped('employee_id'):   # AFTER  (legal; .employee_id would raise)
```

Case 3 is the one that bites. `mapped()` works on any recordset size and reproduces
the old union semantics exactly.

## ⚠️ Pitfalls

- **A green test run proves nothing here.** Report classes, `@api.onchange`
  handlers and button methods are frequently untested; on one 20-module suite the
  automated migration suite passed 82/82 while two live `employee_ids` reads
  survived — in a QWeb report and in a button. Grep the whole tree, don't trust the
  tests: `grep -rn employee_ids --include='*.py' --include='*.xml' .`
- **Filter the grep hits by model before editing.** `employee_ids` is a perfectly
  valid field name on *other* models (wizards, batches, `return.vacation`), and
  `get_employee_ids` / `_compute_employee_ids` are method names. Only the ones on
  `hr.leave` need changing.
- Same removal affects `holiday_type` and the multi-employee helpers
  (`_get_employees_from_holiday_type`, `_prepare_employees_holiday_values`) — if
  your module calls those, it is almost certainly a copied core method: see
  `upgrade/copied-core-method-only-breaks-at-the-upgrade.md`.
- Odoo 18 also made `hr.leave.type.requires_allocation` a Selection
  (`'yes'`/`'no'`, `required=True`). Test fixtures passing a Boolean fail with
  `NotNullViolation` on `requires_allocation`.

## Verification

```bash
# The field really is gone (only a local variable matches):
grep -n "employee_ids" addons/hr_holidays/models/hr_leave.py

# The ensure_one() that makes case 3 mandatory:
sed -n '1238,1242p' odoo/fields.py     # "# only a single record may be accessed"

# Then exercise the untested paths yourself -- a report on TWO records, not one:
./odoo-bin shell -c <conf> -d <db> --no-http
>>> env['report.<module>.<name>']._get_report_values([leave1.id, leave2.id])
```

## References

- Core: `addons/hr_holidays/models/hr_leave.py` (17.0 line 205 → absent in 18.0)
- Core: `odoo/fields.py:1227` `Field.__get__` → `record.ensure_one()`
- Related file: `upgrade/hr-leave-number-of-days-display-removed-odoo19.md`
- Related file: `upgrade/hr-employee-address-home-id-deprecation-odoo17.md`
- Related file: `upgrade/copied-core-method-only-breaks-at-the-upgrade.md`
