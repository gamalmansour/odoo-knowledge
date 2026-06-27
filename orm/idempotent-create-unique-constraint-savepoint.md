# Idempotent create against a unique SQL constraint — allocate the key, don't rely on a default, and wrap in a savepoint

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `constraints`, `unique`, `savepoint`, `IntegrityError`, `idempotency`, `period_index`

---

## Problem

A button/flow that "loads or creates" a child record (here: `ss.tm.compliance` checkpoints created from a `sale.visit`) crashes with an `IntegrityError` that rolls back the **entire** save, even though the code has an "idempotency" search meant to avoid duplicates.

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "ss_tm_compliance_unique_checkpoint"
DETAIL:  Key (contract_line_id, branch_id, period_index)=(42, 7, 1) already exists.
```

Two independent defects were behind the same button:

1. **Wrong model for the gating field.** The code read `line.compliance_mode`, but `compliance_mode` is a field on the **parent** `ss.tm.contract`, not on `ss.tm.contract.line`. Plain attribute access on a model that doesn't define the field raises `AttributeError` at runtime (this is *not* the registry-load `KeyError` of a bad `related=` — see `orm/related-field-keyerror-reference.md`).
2. **Relying on a field default for a uniqueness key.** The create omitted `period_index`, which defaults to `1`. The table has `unique(contract_line_id, branch_id, period_index)`. The idempotency search keyed on a **date range**, not on `period_index`, so a second visit to the same line+branch — or a visit after a scheduled run already wrote a `period_index = 1` row whose date fell outside the search window — tried to insert a second `period_index = 1` row and violated the constraint.

## Root Cause

- A uniqueness key was being populated by a static field **default** instead of being **allocated** against existing rows. Any second writer for the same `(parent, branch)` reuses `1` and collides.
- The "idempotency" guard searched on a *different* set of columns (a date range) than the columns the SQL constraint actually enforces. An idempotency check must key on the **same tuple** as the constraint, or it will let colliding inserts through.
- A single raw `create()` inside a larger transaction means one constraint hit aborts the whole transaction (the user's entire save), instead of being contained.

## Solution ✅

1. Reference the gating field on the model that actually owns it: `line.contract_id.compliance_mode`.
2. Allocate the next free value of the unique key instead of trusting the default:

```python
def _tm_next_period_index(self, contract_line, branch):
    self.ensure_one()
    existing = self.env['ss.tm.compliance'].sudo().search([
        ('contract_line_id', '=', contract_line.id),
        ('branch_id', '=', branch.id),
    ])
    indexes = existing.mapped('period_index')
    return (max(indexes) + 1) if indexes else 1
```

3. Contain a residual race (two visits, or a concurrent scheduled `action_generate_compliance`) in a savepoint so a constraint hit degrades to a logged skip instead of poisoning the transaction:

```python
import psycopg2
period_index = visit._tm_next_period_index(line, branch)
try:
    with self.env.cr.savepoint():
        Compliance.create({
            'contract_line_id': line.id,
            'branch_id': branch.id,
            'visit_id': visit.id,
            'date': visit.visit_date,
            'period_index': period_index,
            'status': 'pending',
        })
except psycopg2.IntegrityError:
    _logger.warning("Skipped duplicate checkpoint for line %s / branch %s / period %s.",
                    line.id, branch.id, period_index)
```

## ⚠️ Pitfalls

- **`with self.env.cr.savepoint():` flushes on entry AND on exit** (`_FlushingSavepoint` in `odoo/sql_db.py`). The deferred INSERT — and therefore the `IntegrityError` — fires on the **exit flush**, then the savepoint rolls back and re-raises, so the `try/except` around the `with` block catches it and the outer transaction stays alive. You do **not** need a manual `flush()` inside the body; you **do** need the `try/except` to wrap the whole `with`, not a line inside it.
- Catch `psycopg2.IntegrityError` (a unique violation is the subclass `psycopg2.errors.UniqueViolation`). Odoo 19 still ships `psycopg2`.
- Don't "fix" this by widening the idempotency search alone — if the search and the constraint don't key on the **same columns**, you only move the race. Allocate the key.
- `--test-enable` forces Odoo to spawn the HTTP server even with `--stop-after-init`/`--no-http` (`server.py`: `if config['test_enable'] or ...: http_spawn()`). When a dev server is already running, pass free `--http-port` and `--gevent-port` or the test process dies with `OSError: [Errno 48] Address already in use` before any test runs.

## Verification

```bash
# Isolated DB, free ports so it won't fight the running dev server
.venv/bin/python odoo-bin -c odoo19_dev.conf -d test_db --without-demo=True \
  -i ss_trade_marketing_visit --test-enable --test-tags /ss_trade_marketing_visit \
  --stop-after-init --http-port 8911 --gevent-port 8912 --max-cron-threads=0
# => odoo.tests.result: 0 failed, 0 error(s) of 4 tests
```

## References

- Related file: `orm/related-field-keyerror-reference.md` (the *registry-load* failure mode for `related=` paths — distinct from this runtime `AttributeError`)
- Related file: `orm/write-override-atomicity-pattern.md` (transaction atomicity around `super()`)
- Code: `ss_trade_marketing_visit/models/sale_visit.py` (`_tm_next_period_index`, `action_load_tm_checkpoints`)
