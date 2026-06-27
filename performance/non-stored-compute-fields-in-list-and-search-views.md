# Non-Stored Computed Fields in List/Search Views → Full Re-Scan Per Render

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | performance                                |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `performance`, `computed-fields`, `store`, `list-view`, `search`, `read_group`, `scaling`

---

## Problem

> A `store=False` computed field is placed in a tree (list) view, used in a search filter, or in a group-by. Every time the list renders, sorts, filters, or groups by that column, Odoo recomputes it for **every row on the page** — and if the compute itself scans other tables, you get a full multi-table scan per render. It feels instant in a demo and becomes multi-second page loads after a year of data.

```python
# sale_target.py — 24 achievement fields like this, ALL rendered in the tree view:
achieved_amount = fields.Monetary(compute='_compute_achievement')        # store=False (default)
achievement_pct = fields.Float(compute='_compute_achievement')           # store=False

def _compute_achievement(self):
    for target in self:                       # per-row
        moves = self.env['account.move.line'].search([...])   # full scan, no index, per row
        # + sale.visit scan + crm.lead scan ...
```

## Root Cause

A non-stored compute has **no column, no value, no index** in the database. The ORM cannot `SELECT` it — it must run the Python `compute` at read time. In a list view that means once per visible row; in a `read_group`/pivot it runs across the whole filtered set. There is no cache to fall back on, so cost grows linearly (or worse, quadratically for team/rollup computes) with the source tables — exactly the tables (`account.move.line`, `sale.visit`) that grow fastest.

## Solution ✅

> Two valid strategies — pick by how often the source data changes.

```python
# A) Source data settles → make it STORED with a NARROW trigger set, so it's a real column:
achievement_pct = fields.Float(compute='_compute_achievement', store=True)

@api.depends('target_amount', 'order_line_ids.price_total')   # only what truly affects it
def _compute_achievement(self):
    ...

# B) Source data changes constantly (live aggregates) → keep store=False but
#    REMOVE the field from the tree/search/group-by; show it only on the FORM.
#    Optionally add a nightly cron that writes a stored snapshot column for reporting.
```

Always prefer a single `read_group()` over a `search()`-per-row inside the compute (see `performance/n-plus-one-queries-computed-fields.md`).

## ⚠️ Pitfalls

- `store=True` with a **broad** `@api.depends` is its own trap: it triggers mass recompute on every change to a popular source field. Narrow the dependencies.
- You cannot sort, filter, or group by a `store=False` field efficiently — the DB has nothing to order. If users need to sort/filter it, it must be stored.
- Stored computed fields used in domains/group-by usually also want `index=True`.
- Team/manager rollup computes that `search()` per record cascade recompute into every child — batch them with one `read_group` over the whole recordset.

## Verification

```bash
# Find non-stored computes that appear in tree/search views
grep -rn "compute=" custom/<module>/models/ | grep -v "store=True"
# Cross-check those field names against <tree>/<list> and <search> in views/
```

## References

- Related file: `performance/n-plus-one-queries-computed-fields.md`
- Related file: `sale/sales-target-crm-won-customers-cartons.md`
