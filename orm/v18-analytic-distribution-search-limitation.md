# V18 Analytic Distribution Search Limitation on Account Moves

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `analytic_distribution`, `account.move.line`, `search`, `orm`, `v18`

---

## Problem

When attempting to filter or search journal entries (`account.move`) or journal items (`account.move.line`) using standard domain expressions against the `analytic_distribution` field:

```python
moves = env['account.move'].search([('line_ids.analytic_distribution', 'like', '9')])
```

Odoo raises an unhandled exception:

```
File "/Users/gamal/odoo/odoo18.0/addons/analytic/models/analytic_mixin.py", line 81, in _condition_to_sql
    raise UserError(_('Operation not supported'))
odoo.exceptions.UserError: Operation not supported
```

## Root Cause

Starting in Odoo 16 and continued through Odoo 18, `analytic_distribution` is implemented via `analytic.mixin` as a serialized JSON dictionary field (e.g., `{"9": 100.0}`). In `analytic_mixin.py`, `_condition_to_sql` explicitly raises `UserError('Operation not supported')` when standard ORM operators like `like`, `ilike`, or `=` are applied directly in relational domain leaves.

## Solution ✅

Instead of querying `account.move` or `account.move.line` directly through the JSON field, query the underlying relational model `account.analytic.line`, which holds the actual relational foreign keys:

```python
# Query analytic postings directly
analytic_lines = env['account.analytic.line'].search([
    ('account_id', '=', analytic_account_id)
])

# To retrieve the parent accounting moves
parent_moves = analytic_lines.move_line_id.move_id
```

## ⚠️ Pitfalls

- Never write SQL injection workarounds or direct JSON operator string lookups in cross-version custom addons.
- Avoid traversing Many2one relations through `line_ids.analytic_distribution` in search domains or action window filters.

## Verification

```python
analytic_lines = env['account.analytic.line'].search([('account_id', '=', 9)])
assert analytic_lines, "Analytic lines successfully retrieved without UserError"
```
