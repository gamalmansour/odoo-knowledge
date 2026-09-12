# A Cron That Writes Derived Values Back onto the Source Field Silently Zeroes It

| Field         | Value                     |
|---------------|---------------------------|
| Category      | orm                       |
| Odoo Versions | All                       |
| Severity      | 🔴 Critical               |
| Last Verified | 2026-09-12                |
| Author        | ENG/Gamal Mansour         |

**Tags:** `cron`, `ir.cron`, `compute`, `store`, `payroll`, `data-loss`, `silent-failure`

---

## Problem

An hourly scheduled action ran over **every** `hr.contract` in the database and rebuilt
`wage` and the allowances from a "salary history" one2many:

```python
class ContractScheduler(models.Model):
    _name = 'contract.scheduler'

    def run_compute_total_salary(self):
        contracts = self.env['hr.contract'].search([])   # every contract, every company
        for rec in contracts:
            rec.compute_total_salary()
```

```python
def compute_total_salary(self):
    inc_wage = dec_wage = 0
    for rec in self.contract_history_line_ids:
        inc_wage += sum(rec.filtered(lambda r: r.type == 'increase').mapped('wage'))
        dec_wage += sum(rec.filtered(lambda r: r.type == 'decrease').mapped('wage'))
    total_wage = inc_wage - dec_wage
    self.wage = total_wage          # <-- unconditional, outside any guard
```

Nothing in the codebase created `hr.contract.history.line` records — they were manual
entry only. A contract with no history lines therefore summed to **zero**, and the cron
wrote `wage = 0` onto it. Hourly. On every contract.

## Root Cause

Two separate mistakes compound:

1. **A derived value is written back onto its own source.** `wage` is the input a human
   maintains; the history lines are a log *about* it. Writing the aggregate of the log
   back onto the input means an empty log erases the input. A one-way compute
   (`total_salary = wage + allowances`) has no such failure mode.
2. **The accumulator's empty case was never considered.** `sum()` over nothing is `0`, and
   `0` is a perfectly valid wage as far as the ORM is concerned — no constraint, no
   warning, no log line.

There was a second, unrelated bug that partly masked the first:
`other_allowance_tags` is a `Many2many`, so `sum(recordset)` raises `TypeError` — the cron
died and rolled back its transaction on any database that *did* have history lines. So the
damage was all-or-nothing, decided by whether anyone had ever filled the log:

| Database state | What the hourly cron did |
|---|---|
| No contract has history lines | Committed — **every wage set to 0** |
| Any contract has history lines | `TypeError`, whole transaction rolled back, nothing written |

## Solution ✅

> Make the derived field a one-way stored compute, and leave the source alone.

```python
total_salary = fields.Monetary(
    string='Total Salary', compute='_compute_total_salary', store=True,
    help="Gross salary used as the base for end-of-service gratuity. "
         "Computed from the contract fields, never written to directly.")

@api.depends('wage', 'l10n_sa_housing_allowance', 'l10n_sa_transportation_allowance',
             'food_allowance', 'l10n_sa_other_allowances')
def _compute_total_salary(self):
    for rec in self:
        rec.total_salary = (rec.wage + rec.l10n_sa_housing_allowance
                            + rec.l10n_sa_transportation_allowance
                            + rec.food_allowance + rec.l10n_sa_other_allowances)
```

The history lines become a read-only audit trail. The cron is then unnecessary: the ORM
recomputes a stored compute on its own.

### You usually cannot delete the cron method

The `ir.cron` record lived in a `noupdate="1"` data file, so setting `active` to `False`
in XML **never reaches a database where the record already exists** (see
[noupdate-group-change-never-reaches-existing-databases.md](../security/noupdate-group-change-never-reaches-existing-databases.md)).
Deleting the Python method would turn a harmless cron into an hourly traceback. Keep the
entry point, empty it, and say so:

```python
@api.model
def run_compute_total_salary(self):
    """No-op kept alive for the existing scheduled action, which lives in a
    noupdate="1" file and cannot be disabled from XML."""
    _logger.info("Scheduled action 'Compute Total Salary' is obsolete and did nothing.")
    return True
```

Then tell the operator to disable it in **Settings → Technical → Scheduled Actions** —
that step is theirs, not the module's.

## ⚠️ Pitfalls

- `search([])` inside a cron is the tell. A cron that touches every row of a business
  table needs a very good reason and always needs a domain.
- An **unassigned stored compute does not raise.** `odoo/fields.py:1227` only raises
  `Compute method failed to assign` when `self.readonly and not self.store`; a stored
  field silently falls back to `False`/`0`. A compute with a missing `else` branch
  therefore zeroes the field instead of erroring — the same silent shape as this bug.
- A stored compute **without `@api.depends`** computes once at creation and never again.
  It looks like a working field for months.
- `sum()` over a `Many2many`/`One2many` `mapped()` raises `TypeError`, it does not return
  0 — check what `mapped()` actually yields before summing.
- Write the regression test against the *empty* case (`assertFalse(rec.history_ids)` then
  assert the wage survived). Testing the populated path proves nothing here.

## Verification

```bash
# Find crons that sweep a whole table
grep -rn "search(\[\])" --include="*.py" <addons> | grep -i cron

# Confirm which crons are live, and what they run (ir.cron inherits ir.actions.server)
psql -d <db> -c "SELECT c.id, c.active, c.interval_number||' '||c.interval_type, a.code
                 FROM ir_cron c JOIN ir_act_server a ON a.id = c.ir_actions_server_id;"
```

## References

- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Odoo source: `odoo/fields.py:1216-1231` (the unassigned-compute fallback)
