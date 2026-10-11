# Sales KPI Standard Target Pollution by Salesperson Past Actuals

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `kpi`, `crm`, `sales`, `standard-target`, `computed-fields`, `store`

---

## Problem

In CRM / Sales KPI goal trackers, standard baseline targets (such as required leads, meetings, ongoing deals, and closed transactions) suddenly evaluate to `0.0` for active or returning salespersons.

For example, a senior salesperson with an established baseline requirement of 3 closings and 9 ongoing deals shows `req_ongoing: 0.0` and `transaction: 0.0` on their quarterly tracker.

## Root Cause

A common architectural flaw in KPI compute methods (`get_standard_fields`) is branching between "new salespersons" and "returning salespersons":
- For new reps, it reads the baseline figures from the standard configuration model (`kpis.standard.target`).
- For returning reps, it rolls forward their **actual past month performance** into the standard target fields (`rec.transaction = previous_month_line.closed_tcr`).

When a salesperson has a slow or deal-free month (e.g. closed 0 TCR deals), copying their actual performance into standard target fields zeroes out their baseline requirements, corrupting KPI achievement metrics and managerial reviews.

Furthermore, when compute fields compute both stored and non-stored fields (`std_avg_unit_value` without `store=True`), Odoo issues a cache inconsistency warning:
```
UserWarning: kpis.goal.tracker: inconsistent 'store' for computed fields, accessing std_avg_unit_value may recompute and update target_amount...
```

## Solution ✅

1. **Decouple Theoretical Standard Targets from Personal Actuals:**
   The `Standard Target (Default)` section must strictly read from the theoretical baseline matrix (`kpis.standard.target`) regardless of whether the rep is new or returning.

```python
@api.depends('job_position_matrix_id', 'company_id', 'months_ids')
def get_standard_fields(self) -> None:
    for rec in self:
        rec.std_avg_unit_value = 0.0
        rec.target_amount = 0.0
        rec.req_lead = 0.0
        rec.req_meeting = 0.0
        rec.req_ongoing = 0.0
        rec.transaction = 0.0

        if rec.job_position_matrix_id and rec.company_id:
            standard_record = rec._standard_target()
            if standard_record:
                rec.target_amount = standard_record.target_amount or 0.0
                rec.std_avg_unit_value = standard_record.avg_unit_value or 0.0
                rec.req_lead = standard_record.req_lead or 0.0
                rec.req_meeting = standard_record.req_meeting or 0.0
                rec.req_ongoing = standard_record.req_ongoing or 0.0
                rec.transaction = standard_record.req_closing or 0.0
```

2. **Ensure Consistent `store=True`:**
   Add `store=True` to all fields sharing the compute method to avoid cache invalidation loops.

3. **Recompute Existing Trackers in DB:**
```python
env['kpis.goal.tracker']._cron_update_standard_fields()
env.cr.commit()
```

## ⚠️ Pitfalls

- **Do Not Test Before Upgrading Schema:** If you add `store=True` to a previously non-stored field, running `--test-enable` without first running `-u <module>` will fail with `psycopg2.errors.UndefinedColumn: column does not exist`.
- **Preserve Manual Goals:** Only populate `goal_target_in_quarter` if `not rec.goal_target_manual`, allowing managers to set custom targets without them being wiped by cron runs.

## Verification

Run the test suite with `-u`:
```bash
python3 odoo-bin -c lexies.conf -d lxet_stage -u lxet_kpis --test-enable --test-tags /lxet_kpis --stop-after-init
```
Verify via shell that returning reps retain non-zero standards:
```python
tracker = env['kpis.goal.tracker'].browse(219)
assert tracker.transaction > 0.0
assert tracker.req_ongoing > 0.0
```
