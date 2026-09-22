# KPI Quarterly Accumulation vs Current Month Pacing & Real-Time Sync from Transactions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `kpi`, `goal-tracker`, `accumulation`, `real-time-sync`, `cron-vs-orm`, `crm-lead`

---

## Problem

In CRM & Sales KPI Goal Tracking systems, quarterly targets are broken down into monthly pacing sub-lines (`goal.tracker.month.line`), while the main quarterly tracker (`kpis.goal.tracker`) displays both **Current Month** and **Current Quarter** metrics.

Two critical defects commonly occur:
1. **Empty / Blind Current Quarter:** The accumulation logic for `Current Quarter` filters with `date < 1st_of_current_month` under the assumption that "Quarter accumulation should only sum completed/finished months". As a result, during the active quarter, all activities (leads, meetings, deals) performed in the current month are completely excluded from the quarter metrics. In month 1 of any quarter, the entire quarter status shows `0.00`!
2. **Stale UI on Browser Refresh:** The `Current Month` and `Current Quarter` status fields on the parent tracker are stored plain floats updated solely by a nightly scheduled action (`cron`). When a salesperson is assigned a lead or closes a deal in CRM, refreshing the Goal Tracker browser page continues to display outdated/zero values until the next night.

## Root Cause

1. **Flawed Domain Boundary in Accumulation:** The query for quarterly accumulation was written as:
   ```python
   # BUG: Excludes the ongoing month from the quarter total
   if current_month in quarter_months:
       finished_lines = line_model.search([
           ("tracker_id", "=", month_record.id),
           ("date", "<", date(current_year, current_month, 1)),
           ("date", ">=", date(current_year, min(quarter_months), 1)),
       ])
   ```
   This violated standard business specifications (e.g. GT-005 "Current Quarter: The three months accumulated") which require quarter-to-date (QTD) accumulation.

2. **Decoupled Lifecycle:** `crm.lead` and `commission.tcr` recomputed the child month lines (`goal.tracker.month.line._compute_stage_values()`), but did not trigger an update on the active parent `kpis.goal.tracker` recordset.

## Solution ✅

1. **Correct Quarterly Accumulation Logic:**
   Accumulate all months of the quarter to date (inclusive of current month):
   ```python
   if current_month in quarter_months:
       quarter_end_date = (date(current_year, current_month, 1) + relativedelta(months=1, days=-1))
       accumulated_lines = line_model.search([
           ("tracker_id", "=", month_record.id),
           ("date", "<=", quarter_end_date),
           ("date", ">=", date(current_year, min(quarter_months), 1)),
       ])
   else:
       accumulated_lines = line_model.search([
           ("tracker_id", "=", month_record.id),
           ("date", ">=", date(current_year, min(quarter_months), 1)),
           ("date", "<=", date(current_year, max(quarter_months), 28) + relativedelta(days=3)),
       ])
   ```

2. **Make Update Method Support Target Recordsets & Trigger from Source:**
   Allow the update routine to run directly on `self`:
   ```python
   trackers = self if self else self.search([])
   for tracker in trackers:
       ...
   ```
   And in `crm.lead`:
   ```python
   def _recompute_goal_tracker_lines(self):
       for lead in self:
           if not lead.user_id:
               continue
           tracker_lines = self.env["goal.tracker.month.line"].search([
               ("tracker_id.user_id", "=", lead.user_id.id),
           ])
           tracker_lines._compute_stage_values()
           
           user_trackers = self.env["kpis.goal.tracker"].search([
               ("user_id", "=", lead.user_id.id),
               ("state", "=", "running"),
           ])
           if user_trackers:
               user_trackers._cron_update_current_and_prev_month_status()
   ```

## ⚠️ Pitfalls

- **Avoid Full Table Scans in CRM Hooks:** Never call `_cron_update_current_and_prev_month_status()` on `env['kpis.goal.tracker'].search([])` inside a `crm.lead` write hook. Always filter to `user_id = lead.user_id` and `state = 'running'`.
- **Database Transaction Commit in Shell:** Remember that testing in Odoo shell does not commit by default. Always execute `env.cr.commit()` if you expect browser UI sessions to see values immediately.
- **Stage Flag Alignment:** Ensure stage boolean flags (`is_lead`, `is_meeting`, `is_ongoing`) accurately reflect stage names, otherwise counters will increment in unexpected categories (e.g., a lead in a "Meeting" stage increments `meeting`, not `lead`).

## Verification

```bash
# Run targeted unit tests
python3 odoo-bin -c lexies.conf -d lxet_stage --test-enable --stop-after-init --test-tags=/lxet_kpis
```
Result should be `0 failed, 0 error(s)`.
