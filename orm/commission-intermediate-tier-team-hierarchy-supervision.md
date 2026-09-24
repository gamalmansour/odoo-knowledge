# Multi-Level Commission Hierarchy & Supervision Cut Architecture in Real Estate Brokerage

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `commission`, `hierarchy`, `supervision-cut`, `kpi`, `goal-tracker`, `brokerage`, `crm-team`

---

## Problem

When introducing an intermediate management level (such as `Team Leader`) between `Sales Manager` and `Property Consultant` in a multi-tier brokerage structure, supervision commission (`cut`) and personal commission (`personal`) often silently compute as `0.0 EGP` on deal (TCR) approvals, or the supervision chain fails to cascade cuts to higher directors.

Specifically:
1. The Team Leader earns 0 cut on their subordinates' deals.
2. The Team Leader's own personal deals generate cuts for the Team Leader himself, or fail to reward the Sales Manager/Director above.
3. The Sales Manager's cut drops to 0 because team target aggregation misses intermediate members.

## Root Cause

1. **Hierarchy Traversal Logic (`_supervision_chain`)**:
   The engine reads ordered records from `commission.team.hierarchy` top-down and breaks when `line.user_id == agent_id`. All records above the agent in that ordered sequence are collected and reversed (closest manager first). If the subordinate (e.g. Property Consultant) is NOT listed in the hierarchy, the loop never breaks and collects everyone. If the intermediate manager (e.g. Team Leader) is missing or mis-sequenced, the cascade breaks.
2. **Goal Tracker Team Line Dependency (`_get_team_target`)**:
   In `_get_team_target(manager, job_matrix, rec)`, the manager's target is computed as `sum(kpi.team_line.mapped('target_amount'))`. If `team_target == 0` (e.g., no `team_line` configured for that manager in the current quarter), the method immediately returns `0.0`. Furthermore, `team_tcrs` filters deals by `('agent_id', 'in', team_lines.mapped('agent_id').ids)`. If the closing agent is not explicitly listed in the manager's `team_line`, the manager's achievement is calculated as 0% and defaults to either the lowest tier or 0.

## Solution ✅

When adding an intermediate tier like `Team Leader`:

1. **Job Position & Matrix**:
   Create the general `commission.job.position` with `parent_id = Sales Manager`, and create the company matrix in `commission.job.position.matrix` with continuous policy slabs (`commission_policy_ids`) specifying both personal commission and cut rates per 1M.
2. **User Linkage**:
   Set `user.job_id = team_leader_matrix.id`.
3. **Team Hierarchy Ordering**:
   In `commission.team.hierarchy`, order members strictly by `sequence`:
   - Seq 10: Franchise Owner (`gets_commission = False`)
   - Seq 20: Sale Director (`gets_commission = True`)
   - Seq 30: Sales Manager (`gets_commission = True`)
   - Seq 40: Team Leader (`gets_commission = True`)
   - Seq 50: Property Consultant (`gets_commission = True`)
4. **Dual Goal Tracker Linking**:
   - Create `kpis.goal.tracker` for the Team Leader with `team_line` pointing to their consultants (`target_amount > 0`).
   - Update the Sales Manager's `kpis.goal.tracker` to include BOTH the Team Leader and the Consultants in their `team_line`.

## ⚠️ Pitfalls

- **Do NOT omit consultants from `commission.team.hierarchy`**: Even though consultants do not earn cuts, their presence at the bottom of the hierarchy provides the termination condition (`line.user_id == self.agent_id: break`) for `_supervision_chain`.
- **Calendar Quarter Matching**: TCR dates must fall inside the active quarter (`start_q` to `end_q`, e.g. July 1 to Sept 30 for Q3) for team TCRs to be aggregated for tier achievement.
- **Job Matrix Mismatch**: When inserting hierarchy lines, ensure `job_matrix_id` points to the specific franchise company's matrix, not the general position or another company's matrix.

## Verification

Run test TCRs:
1. **Agent = Team Leader**: Verify Team Leader gets `personal`, Sales Manager gets `cut`, Sale Director gets `cut`, and Team Leader does NOT get a cut on their own deal.
2. **Agent = Consultant**: Verify Consultant gets `personal`, Team Leader gets `cut`, Sales Manager gets `cut`, Sale Director gets `cut`.
