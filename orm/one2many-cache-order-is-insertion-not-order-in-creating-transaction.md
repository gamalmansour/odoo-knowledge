# One2many Recordset Order Is INSERTION Order (not `_order`) Inside the Creating Transaction

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `one2many`, `_order`, `cache`, `computed-fields`, `first-line`, `min`

---

## Problem

A stored compute needs "the FIRST line" of a One2many (e.g. `sale.visit.plan.plan_date` = date of the first visit line, where the line model has `_order = 'visit_date, sequence'`). The obvious implementation:

```python
first_line = plan.plan_line_ids[:1]
```

works when reading an existing record, but returns the **wrong line during the very create() that made the lines** (e.g. an Excel import): with lines supplied as dates 10, 3, 20, `[:1]` returned the *10* line, not the *3* one.

## Root Cause

Inside the creating transaction the One2many value lives in the ORM **cache**, populated in the order the `(0, 0, vals)` commands were processed — **insertion order**. The comodel's `_order` is applied by SQL `ORDER BY` only when the relation is re-fetched from the database, which does not happen mid-create. So `recordset[0]` ≠ "first per `_order`" until a later, fresh read.

Bonus gotcha from the same task: `@api.depends('plan_line_ids.visit_date')` alone did NOT trigger recompute when a line was **unlinked** — the relation itself (`'plan_line_ids'`) must also be in the depends.

## Solution ✅

Derive the "first" line's value instead of indexing, so cache order is irrelevant. When `_order` starts with the field you need, "first line's value" ≡ `min()`:

```python
@api.depends('plan_line_ids', 'plan_line_ids.visit_date')
def _compute_plan_date(self) -> None:
    for plan in self:
        line_dates = [d for d in plan.plan_line_ids.mapped('visit_date') if d]
        if line_dates:
            plan.plan_date = min(line_dates)
        elif not plan.plan_date:
            plan.plan_date = False
```

If you genuinely need the record (not just its value), sort explicitly with the `_order` keys: `plan.plan_line_ids.sorted(key=lambda l: (l.visit_date, l.sequence))[:1]` — but avoid `l.id` in the key (NewId records are not reliably comparable).

## ⚠️ Pitfalls

- **`recordset[:1]` on a One2many is only `_order`-correct on a fresh DB read** — never inside the transaction that created/modified the lines.
- **Include the relation field itself in `@api.depends`** (`'line_ids'` alongside `'line_ids.field'`) or unlinking a line silently leaves the compute stale.
- **Use compute, not onchange**, when the client imports via Excel — see [onchange-only-computation-breaks-nonform-create](onchange-only-computation-breaks-nonform-create.md).
- Verify with an import-style plain `create()` in `odoo shell`, not through the form — the form path hides the cache-order problem.

## Verification

Shell scenario on Odoo 19 (`sale_visit`): create plan with line dates (10, 3, 20) via plain ORM create → `[:1]` version returned 10 (wrong); `min()` version returns 3 (correct). Unlink of the earliest line only recomputes when `'plan_line_ids'` is in depends. Regression tests: `sale_visit/tests/test_plan_date_from_lines.py`.

## References

- Related file: [sale_visit/models/sale_visit_plan.py](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/models/sale_visit_plan.py)
- Related KB: [onchange-only-computation-breaks-nonform-create](onchange-only-computation-breaks-nonform-create.md), [stored-compute-incomplete-depends-silent-staleness](stored-compute-incomplete-depends-silent-staleness.md)
