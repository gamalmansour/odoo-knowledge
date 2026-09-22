# Odoo Unit Testing: Magic create_date Ignored on Create & Lazy Compute Invalidation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19, All                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `testing`, `unit-tests`, `create_date`, `lazy-compute`, `invalidate_recordset`, `orm`

---

## Problem

When writing unit tests (`TransactionCase`) in Odoo that simulate historical timelines, monthly status tracking, or date-dependent algorithms, two common failures occur:

1. **Backdated `create_date` is Silently Ignored:** Passing `'create_date': datetime(...)` in `model.create({...})` does not backdate the record. Odoo sets `create_date` to `fields.Datetime.now()`. Date-bounded queries (e.g. `[('create_date', '<=', end_date)]`) will return empty recordsets, causing test assertion failures.
2. **Missing `.refresh()` in Odoo ORM:** Using SQLAlchemy's `record.refresh()` raises `AttributeError: '<model>' object has no attribute 'refresh'`.
3. **Lazy Compute Fields in Automated Cron Tests:** Computed relational fields (`One2many` with `compute='_compute_...'`) are evaluated lazily upon explicit access. Calling crons or direct queries via `self.env['other.model'].search(...)` will miss records whose computes have not yet triggered in the current transaction.

```
AssertionError: 0.0 != 1
AttributeError: 'kpis.goal.tracker' object has no attribute 'refresh'
```

---

## Root Cause

1. **Magic Field Behavior:** In Odoo ORM, `create_date`, `create_uid`, `write_date`, `write_uid` are system-managed "magic" fields. The ORM's `create()` method automatically overrides `create_date` with `datetime.now()` regardless of dictionary values passed in `vals`.
2. **Cache vs Database Invalidation:** Odoo recordsets do not have a `.refresh()` method. Instead, cache invalidation is handled by `record.invalidate_recordset()` or `self.env.invalidate_all()`.
3. **Lazy Compute Evaluation:** In memory, compute methods for fields that are not immediately accessed in code or flushed to the SQL tables remain uncalculated.

---

## Solution ✅

### 1. Backdating `create_date` in Tests via SQL

To reliably backdate `create_date` in unit tests, create the record normally with the ORM, then execute a direct SQL UPDATE followed by `invalidate_recordset(['create_date'])`:

```python
def _create_lead(self, create_date, stage='lead'):
    stage_id = self.env['crm.stage'].create({'name': f'{stage}', 'is_%s' % stage: True})
    c_date = datetime.combine(create_date, datetime.min.time())
    lead = self.Lead.create({
        'name': 'Test Lead',
        'user_id': self.user.id,
        'stage_id': stage_id.id,
    })
    # Directly update the magic field in the test transaction
    self.env.cr.execute("UPDATE crm_lead SET create_date = %s WHERE id = %s", (c_date, lead.id))
    lead.invalidate_recordset(['create_date'])
    return lead
```

### 2. Proper Cache Invalidation in Tests

Replace any `.refresh()` calls with:

```python
# Invalidate specific recordset cache
record.invalidate_recordset()

# Or invalidate specific fields
record.invalidate_recordset(['current_status_ongoing', 'current_status_transaction'])
```

### 3. Ensure Computed Relations are Instantiated Before Cron Search

In cron methods or test cases that query child models directly via `self.env['child.model'].search(...)`, defensively ensure the parent compute has executed:

```python
@api.model
def _cron_update_status(self, ref_date=None):
    # Proactively ensure running records have instantiated child records
    for parent in self.search([('state', '=', 'running')]):
        if not self.env['child.model'].search_count([('parent_id', '=', parent.id)]):
            parent._compute_child_records()

    # Now search child lines
    all_lines = self.env['child.model.line'].search([])
    ...
```

---

## ⚠️ Pitfalls

- **Avoid calling SQL UPDATE without cache invalidation:** If you update `create_date` via `self.env.cr.execute` without calling `record.invalidate_recordset(['create_date'])`, the ORM will continue to serve the cached current timestamp.
- **Check Stored Compute Years:** Never hardcode `date.today().year` inside sub-model creation logic (e.g. `goal.tracker.month`). Always check `record.parent_id.year or date.today().year` so historical or test-specified years are respected.

---

## Verification

Run test suites with `--test-enable`:

```bash
python3 odoo-bin -c odoo.conf -d test_db --test-tags=my_module --stop-after-init
```

Result: `0 failed, 0 error(s) of N tests`.
