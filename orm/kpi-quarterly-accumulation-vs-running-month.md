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
3. **Missing Source Hooks on Deals (`commission.tcr`):** While leads update CRM stages, confirmed transactions (`commission.tcr`) have no ORM listeners linked to `goal.tracker.month.line`. As a result, confirmed deals never reduce `Remaining Target` or increment closed transactions until a manual system recalculation occurs.

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

2. **Decoupled Lifecycle & Missing Reverse Hooks:** Neither `crm.lead` nor `commission.tcr` had complete reverse triggers. While `crm.lead` had partial hooks, `commission.tcr` had zero overrides on `create`/`write`/`unlink` to inform `goal.tracker.month.line._compute_stage_values()` or trigger `kpis.goal.tracker._cron_update_current_and_prev_month_status()`.

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

3. **Real-time Synchronizer Hook on `commission.tcr`:**
   Implement an inherited model (`commission_tcr_inherit.py`) overriding `create`, `write`, and `unlink` with defensive change detection:
   ```python
   def _sync_goal_trackers_for_users(self, agent_ids: set[int]) -> None:
       if not agent_ids:
           return
       month_lines = self.env["goal.tracker.month.line"].search([
           ("tracker_id.user_id", "in", list(agent_ids))
       ])
       if month_lines:
           month_lines._compute_stage_values()
       trackers = self.env["kpis.goal.tracker"].search([
           ("user_id", "in", list(agent_ids)),
           ("state", "=", "running"),
       ])
       if trackers:
           trackers._cron_update_current_and_prev_month_status()
   ```

## ⚠️ Pitfalls

- **Avoid Full Table Scans in CRM & TCR Hooks:** Never call `_cron_update_current_and_prev_month_status()` on `env['kpis.goal.tracker'].search([])` inside a write hook. Always filter to `user_id = agent_id` and `state = 'running'`. Furthermore, inside `_cron_update_current_and_prev_month_status()`, scope `all_lines` to `('tracker_id.tracker_id', 'in', self.ids)` when `self` is non-empty.
- **Filter Confirmed TCR Statuses Only:** When computing transaction counts and volume from `commission.tcr`, always explicitly filter by confirmed statuses: `("status", "in", ("approved", "contracted", "collected"))`. Omitting this counts draft or cancelled deals into salesperson quota metrics!
- **Database Transaction Commit in Shell:** Remember that testing in Odoo shell does not commit by default. Always execute `env.cr.commit()` if you expect browser UI sessions to see values immediately.
- **Misleading Naming vs Business Spec:** Naming a quarterly remaining target as `Remaining Target in Month` causes stakeholders to assume targets are split evenly per month (Target ÷ 3), whereas standard business specs (e.g. GT-011) operate on carry-forward of the remaining quarter target. The label should always be `Remaining Target`.
- **Stale Stored Child Values:** Stored computed fields on parent records reflecting child lines (such as `remaining_target_in_month` fetching `months_ids.line_ids.remaining_target`) MUST include `months_ids.line_ids.remaining_target` in `@api.depends`. Omitting child fields causes old/erroneous values (like negative values from old test TCR records) to remain frozen in the database.
- **Stage Flag Alignment:** Ensure stage boolean flags (`is_lead`, `is_meeting`, `is_ongoing`) accurately reflect stage names, otherwise counters will increment in unexpected categories (e.g., a lead in a "Meeting" stage increments `meeting`, not `lead`).

## Verification

```bash
# Run targeted unit tests
python3 odoo-bin -c lexies.conf -d lxet_stage --test-enable --stop-after-init --test-tags=/lxet_kpis
```
Result should be `0 failed, 0 error(s)`.
