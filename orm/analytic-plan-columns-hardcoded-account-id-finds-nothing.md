# Odoo 17 Analytic Plans: a Hard-Coded account_id Domain Finds Nothing

| Field         | Value        |
|---------------|--------------|
| Category      | orm          |
| Odoo Versions | 17, 18       |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `analytic`, `account.analytic.line`, `analytic-plan`, `x_plan_id`, `cost-centre`, `domain`

---

## Problem

The client reported: *"the work-order journal entry is not linked to the cost centre."*

Everything looked correct. The entry was posted, its lines carried the analytic
distribution, and analytic lines were generated:

```sql
SELECT aml.name, aml.debit, aml.analytic_distribution
FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
WHERE am.name = 'MISC/2026/10/0001';
--  WO/2026/00001 - Material | 504000.00 | {"25": 100.0}     <-- tagged correctly
```

Yet the project's "Analytic Costs" button — and every analytic screen — was empty:

```python
env['account.analytic.line'].search([('account_id', '=', 25)])   # -> 0 records
```

## Root Cause

Odoo 17 stores **one column per analytic plan** on `account.analytic.line`. The default
"Projects" plan writes to `account_id`; every other plan gets its own generated column:

```sql
SELECT id, name, amount, account_id, x_plan4_id FROM account_analytic_line;
--  2 | WO/2026/00001 - Material | -504000.00 | (null) |  25
--                                              ^^^^^^   ^^ the value went HERE
```

The suite's project cost centres live on a dedicated **"Construction" plan (id 4)**, so the
distribution `{"25": 100.0}` correctly wrote `x_plan4_id = 25` and left `account_id` NULL.
Every domain hard-coded on `account_id` therefore matched nothing — the cost was landing on
the cost centre the whole time, but no screen could show it, which to the user is
indistinguishable from "not linked at all".

This is invisible until someone uses a non-default plan, which is exactly what a vertical
suite that creates its own plan does.

## Solution ✅

Resolve the column from the account's own plan, the way Odoo does internally
(`analytic/models/analytic_account.py` uses `plan._column_name()` for its own domains):

```python
def _analytic_line_domain(self):
    """Domain matching this project's analytic lines, on the RIGHT plan column."""
    self.ensure_one()
    account = self.analytic_account_id
    if not account:
        return [('id', '=', False)]
    return [(account.plan_id._column_name(), '=', account.id)]

def action_view_analytic_lines(self):
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'account.analytic.line',
        'view_mode': 'tree,form',
        'domain': self._analytic_line_domain(),
    }
```

Verified on the demo database:

```
DOMAIN: [('x_plan4_id', '=', 25)]
LINES FOUND: 3        <-- was 0
```

Sweep for other hard-coded readers:

```bash
grep -rn "account.analytic.line" --include="*.py" . | grep -v _inherit
grep -rn "('account_id', '=', .*analytic" --include="*.py" .
```

## ⚠️ Pitfalls

- `('account_id', '=', False)` as an "empty" guard would return every line of every
  non-default plan — use `[('id', '=', False)]` for a guaranteed-empty domain.
- The same trap applies to `read_group`/`_read_group` aggregations, graph/pivot view
  domains in XML, and any SQL report joining `account_analytic_line.account_id`.
- `_column_name()` returns `account_id` for the default plan, so the dynamic domain is
  correct for both default and custom plans — no branching needed.
- Do not "fix" it by moving the accounts to the default plan: plans are an intentional
  dimension (projects vs departments vs cost codes) and other modules may rely on them.

## Verification

```python
account = project.analytic_account_id
column = account.plan_id._column_name()          # e.g. 'x_plan4_id'
line = env['account.analytic.line'].create({'name': 't', 'amount': -1, column: account.id})
assert line in env['account.analytic.line'].search(project._analytic_line_domain())
```

## References

- Odoo source: `addons/analytic/models/analytic_plan.py` (`_column_name`)
- Odoo source: `addons/analytic/models/analytic_account.py` (internal usage pattern)
- Related file: `views/monetary-column-totals-render-as-dashes.md`
