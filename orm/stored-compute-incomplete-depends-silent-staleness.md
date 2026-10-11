# Stored Compute With Incomplete `@api.depends` → Silent Staleness of Money/KPI Figures

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-27                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `api.depends`, `staleness`, `kpi`, `roi`, `cron`

---

## Problem

> A field is `store=True` with a `compute`, but its `@api.depends` does **not** list the real upstream data that should change the value (often because the upstream lives in another model/module, or is an aggregate the ORM can't trace). The value is computed **once** at create/first-write and then **frozen forever**. A "Refresh" button that only re-reads the record without invalidating doesn't fix it. Management makes bonus/spend decisions on months-old numbers.

```python
# ss_kpi/kpi_evaluation_line.py — score is stored but depends on NOTHING that changes:
score_pct = fields.Float(compute='_compute_score_pct', store=True)

@api.depends('score_raw', 'rating_scale_id.scale_max', 'scoring_type')  # NOT the visits/invoices it represents
def _compute_score_pct(self):
    ...
# Every new visit/invoice/payment during the month does NOT touch score_pct.
# ss_trade_marketing ROI shows the same shape: sales_amount/roi_ratio stored, frozen at save.
```

## Root Cause

Odoo recomputes a stored field **only** when a field named in its `@api.depends` is written. If the true drivers (records in another model, a date-window aggregate, a cross-module field) aren't — or can't be — listed, the recompute never fires. The stored value is correct exactly once and then drifts from reality silently. There is no error; the number just stops matching the data.

## Solution ✅

> Make the refresh **deterministic**. Choose based on whether `@api.depends` can actually express the dependency.

```python
# A) Dependency is expressible → list the REAL drivers (incl. one2many dotted paths):
@api.depends('evaluation_id.visit_ids.state', 'evaluation_id.commission_ids.amount')
def _compute_score_pct(self):
    ...

# B) Driver is a cross-module / date-window aggregate the ORM can't trace →
#    don't pretend it's reactive. Either:
#    (1) make the field store=False (compute on read), OR
#    (2) keep it stored and add an ir.cron that explicitly recomputes open records:
def _cron_refresh_scores(self):
    recs = self.search([('state', 'in', ('draft', 'in_progress'))])
    recs.invalidate_recordset(['score_pct'])
    recs._compute_score_pct()

# C) Recompute on the lifecycle transition that matters, so nothing is approved stale:
def action_submit(self):
    self.invalidate_recordset(['score_pct']); self._compute_score_pct()
    return super().action_submit()
```

A "Refresh" button must call `invalidate_recordset([...])` (or write the values) — re-reading a stored field returns the cached/frozen value and does nothing.

## ⚠️ Pitfalls

- Looks perfect in a same-day demo: you create the record and read it in the same transaction, so the first compute is fresh.
- This pattern is **migration-hostile**: a version bump that triggers a store recompute will suddenly change the frozen numbers (or fail to), shifting money figures during an upgrade.
- Snapshotting (writing the figure onto the record at close time) is a legitimate alternative when you *want* a historical freeze — but then name it clearly and don't expose a misleading "live" value.
- Design the recompute strategy **once at the suite level** if several modules share the shape; patching per-module re-introduces the same bug.

## Verification

```bash
# Stored computes whose depends look suspiciously thin vs. what they represent:
grep -rn -A3 "store=True" custom/<module>/models/ | grep -B1 "api.depends"
# Then: create a record, change an upstream source row, re-read — did the stored value move?
```

## References

- Related file: `orm/testing_compute_fields.md`
- Related file: `orm/compute_cache_warnings_ast.md`
