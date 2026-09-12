# A Stored Compute Built on a Non-Stored One Freezes at Its First Value

| Field         | Value                     |
|---------------|---------------------------|
| Category      | orm                       |
| Odoo Versions | All                       |
| Severity      | 🔴 Critical               |
| Last Verified | 2026-09-12                |
| Author        | ENG/Gamal Mansour         |

**Tags:** `compute`, `store`, `api.depends`, `silent-failure`, `payroll`

---

## Problem

A statutory wage-deduction ceiling was built on the aggregates an older module already
exposed on the payslip:

```python
# hr_ksa_compliance -- WRONG
ksa_deduction_total = fields.Monetary(compute='_compute_deduction_cap', store=True)

@api.depends('loans', 'salary_advance', 'violations', 'contract_id.wage', ...)
def _compute_deduction_cap(self): ...
```

Unit tests passed. Driving it end to end did not: adding a disciplinary penalty to an
employee left the ceiling reporting **zero**. The figure it carried was the one computed
the moment the payslip was created, and nothing ever moved it again.

## Root Cause

`loans`, `salary_advance` and `violations` are themselves **non-stored** computes in the
older module, and their own dependencies are only the payslip's own fields:

```python
# loans_and_addvance
violations = fields.Float(compute='get_violations_line_ids')     # no store

@api.depends('employee_id', 'date_from', 'date_to')              # not the violation records
def get_violations_line_ids(self): ...
```

Odoo builds the trigger tree by walking dependencies transitively. Depending on `violations`
therefore resolves to depending on `employee_id`, `date_from` and `date_to` — nothing else.
Creating a `violations.line` touches none of those, so nothing is invalidated, and a
**stored** field keeps the value already written to its column.

A non-stored field in the same position would have been correct by accident: it recomputes
on every read, so it always sees the current search result.

## Solution ✅

> If any link in the chain is non-stored, or is computed from a `search()` rather than from
> declared dependencies, the field on top of it must not be stored either.

```python
# Not stored: loans / salary_advance / violations are themselves non-stored computes whose
# depends are only (employee_id, date_from, date_to). A stored field on top never
# recomputes when a loan or violation is added.
ksa_deduction_total = fields.Monetary(compute='_compute_deduction_cap')
```

Pin the cause, not only the symptom:

```python
def test_the_ceiling_fields_are_not_stored(self):
    for name in ('ksa_deduction_total', 'ksa_deduction_excess'):
        self.assertFalse(self.env['hr.payslip']._fields[name].store)
```

## ⚠️ Pitfalls

- **The same trap applies to any compute that `search()`es.** A method that searches
  `hr.leave` and sums the result cannot be stored unless a real one2many is declared and
  depended on — the searched records are invisible to the trigger tree.
- Losing `store=True` costs sorting and grouping on that field. If those are needed,
  declare the missing one2many and depend on it properly rather than storing regardless.
- **Unit tests will not catch it.** A test that creates the dependency and the dependent in
  the same transaction usually reads the value before any stale write exists. It takes a
  record created *after* the payslip to expose it — which is what an end-to-end pass does
  and a unit test rarely does.
- Grep for the shape: a stored compute whose `@api.depends` names a field defined in
  another module. Check that field's own `store` and `depends` before trusting it.

## Verification

```python
# In odoo shell, against real records:
slip = env['hr.payslip'].browse(ID)
print(slip.ksa_deduction_total)          # 0.00
# ... create the deduction record ...
slip.invalidate_recordset()
print(slip.ksa_deduction_total)          # must now be non-zero
```

## References

- Related file: `orm/cron-writing-derived-values-back-onto-source-fields.md`
- Related file: `orm/api-depends-on-a-field-declared-in-a-later-module.md`
