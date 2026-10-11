# Tests That Assume an Empty Database Cannot Be Run Where They Matter

| Field         | Value                     |
|---------------|---------------------------|
| Category      | backend                   |
| Odoo Versions | All                       |
| Severity      | 🟡 Medium                 |
| Last Verified | 2026-09-12                |
| Author        | ENG/Gamal Mansour         |

---

**Tags:** `testing`, `TransactionCase`, `constraints`, `deployment`

## Problem

A 59-test suite was green for days. The moment the database was configured the way a client
configures it — GOSI rates entered, sick-leave bands defined, Saudisation bands filled in —
**14 of those tests errored**:

```
ValidationError: Another GOSI rate for Saudi already covers this period.
```

Every failing test created its own configuration row and hit the no-overlap constraint
against the row that was already there. The suite could be run on a throwaway database and
nowhere else — which is the opposite of what a regression suite is for. A client asking
"can you prove the upgrade is safe on our system?" could not be answered.

## Root Cause

`TransactionCase` rolls back, so tests do not *pollute* the database. That is not the same
as being *independent of* it. A test that creates a record subject to a uniqueness or
no-overlap constraint depends on nothing else already satisfying that constraint — an
assumption that holds only while the table is empty.

It is invisible during development because the developer's database is exactly the one the
tests were written against.

## Solution ✅

> Clear the configuration the class is about, in `setUpClass`, inside the test transaction.

```python
@classmethod
def _isolate_ksa_config(cls):
    """Tests must not assume an empty database. On a client system these tables hold the
    real rates, and a test creating its own row hits the no-overlap constraint -- so the
    suite would be unrunnable exactly where it matters most. Rolled back with the rest."""
    company = cls.env.ref('base.main_company')
    for model in ('hr.gosi.rate', 'hr.sick.leave.tier', 'hr.saudization.band',
                  'hr.ramadan.period', 'hr.annual.leave.rule', 'hr.job.grade'):
        if model in cls.env:
            cls.env[model].search([('company_id', '=', company.id)]).unlink()

@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls._isolate_ksa_config()
```

## ⚠️ Pitfalls

- **Do not do this in `setUp`** if the data is created in `setUpClass`: the rollback
  boundaries differ and you will clear records the class still needs.
- Only clear what the class actually creates. Wiping unrelated tables hides real coupling.
- The same applies to counting tests. `test_saudization_percentage` counting employees is
  meaningless on a populated database — exclude pre-existing records explicitly
  (`counts_for_saudization = False`) rather than assuming the count starts at zero.
- **Verify it the only way that proves anything:** run the suite on a database that carries
  real configuration, not a fresh one.

## Verification

```bash
# On a configured database, not a fresh one:
./odoo-bin -c <conf> -d <configured_db> -u <module> --test-enable --test-tags /<module> --stop-after-init
```

## References

- Related file: `orm/stored-compute-on-top-of-a-non-stored-one-never-refreshes.md`
