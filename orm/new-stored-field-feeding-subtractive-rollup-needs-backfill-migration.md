# A new stored field that feeds a SUBTRACTIVE roll-up must be back-filled on upgrade

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `migration`, `stored-compute`, `rollup`, `aggregate`, `money`, `wbs`, `null`, `override`

---

## Problem

You add a per-line dimension field (e.g. `wbs_id` on work-order cost lines) that an
aggregate elsewhere reads to *redistribute* cost — adding lines whose dimension points
here, subtracting lines overridden away:

```python
own_actual = sum(boq_item_ids.mapped('actual_cost'))          # baseline
own_actual += moved_in                                        # lines pointing here
own_actual -= moved_out   # lines whose "home" is here but line.wbs_id != this node
```

On a fresh DB it's correct. After **upgrading an existing DB**, historical rows have the
new column = `NULL`. Every historical line now satisfies `line.wbs_id != node`, so
`moved_out` subtracts them all — **silently zeroing out historical WBS/aggregate costs**.
No error, no traceback; the money numbers just collapse.

## Root Cause

Odoo does not reliably back-fill a new **stored computed** field to its intended default
for existing rows in a way that a subtractive aggregate can trust — and even a plain new
column is `NULL` for history. A subtractive roll-up treats `NULL` (`!= node`) as
"overridden away" and removes the cost.

## Solution ✅

Ship a post-migration that back-fills the new field to its default for every historical
row, then let the dependent aggregate recompute:

```python
# migrations/<new_version>/post-migration.py
from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ('project.material.issue', 'project.labor.record', 'project.equipment.record'):
        recs = env[model].search([('wbs_id', '=', False)])
        if recs:
            recs._compute_wbs_id()                 # default = work_order.boq_item.wbs
            recs.flush_recordset(['wbs_id'])
    env['project.wbs'].search([]).invalidate_recordset(['actual_cost', 'variance'])
```

Bump the module `version` so the migration folder actually runs on upgrade.

## ⚠️ Pitfalls

- Verify AFTER upgrade on a DB **with real history**: query `count(wbs_id != NULL)` and
  confirm a few aggregate totals did not drop. A green test suite on a fresh DB will NOT
  catch this — the bug only exists for pre-existing rows.
- Empty-by-design is fine: if the source (`boq_item.wbs_id`) is itself empty, the line
  stays empty and its cost was never in the aggregate — no subtraction happens. The bug
  is specifically rows whose *default would be non-empty* but sit at `NULL`.
- Keep the aggregate's default path a no-op: when `line.wbs_id == home`, `moved_in` and
  `moved_out` must both exclude it, so an un-overridden line changes nothing.
- Mirror any existing sibling logic (here: subcontract-invoice lines already redistributed
  by their own `wbs_id`) so the two paths stay consistent.

## Verification

```bash
odoo-bin -c conf -d <db_with_history> -u <module> --test-enable \
  --test-tags /<module>:TestWbsCostAttribution --no-http --stop-after-init   # 0 failed
# then, in shell, on the upgraded DB:
#   count lines with wbs_id set, and assert WBS actual_cost totals are unchanged (non-zero)
```

## References

- Related file: `orm/stored-compute-incomplete-depends-silent-staleness.md`
- Related file: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
