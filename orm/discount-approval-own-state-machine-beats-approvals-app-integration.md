# Tiered discount approval: an own-record state machine beats wiring the Approvals app

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All (verified 19)                          |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-08-04 (v3: generalized to an N-tier ladder) |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `architecture`, `workflow`, `approval`, `state-machine`, `sale`, `discount`, `approvals-app`, `escalation`

---

## Problem

Requirement: quotation discount above limit A → the salesman's **own manager**
approves; above limit B → escalates to the **Commercial Director**; approvers
need a dashboard. First implementation glued `sale.order` to the Enterprise
**Approvals app** (`approval.request` + category with
`manager_approval='required'` + programmatically added director approvers).
Review found the control was hollow.

## Root Cause (why the Approvals-app glue failed)

The approval state lived in **another model** linked by a Many2one, so:
- The request never knew **which percentage** it approved → once a request was
  `approved`, ANY later discount (raise to 90% after a 15% approval) confirmed
  freely — the classic unbound authorization
  ([[amount-bound-override-authorization-for-a-hard-block]]).
- Tier selection happened once at request creation; raising the discount while
  pending kept the old (weaker) approver set.
- `approver_ids` is a **computed** field in the Approvals app (Command.clear()
  inside) — manually created `approval.approver` rows can be wiped by a
  recompute; the manager approver silently depends on HR data (no employee /
  no manager ⇒ raw "add at least 1 approvers" UserError at confirm time).
- Sequential escalation isn't the app's native shape (parallel approvers;
  `approver_sequence` exists but adds config surface).

## Solution ✅

Own the workflow on the record itself (`solargy_sale_approval` v2.0.0,
depends `sale_management, hr` — no `approvals`):

- `discount_approval_state`: `none → manager → director → approved / refused`
  (tracking=True, copy=False), plus `discount_requested_pct` and
  `discount_approved_pct` snapshots.
- `action_confirm` guard: allowed when max line discount ≤ limit, or state is
  `approved` **and** max ≤ `discount_approved_pct`. Batch-safe: confirm the
  compliant subset via `super(cls, remaining)`, return one notification for
  the blocked ones (no mid-loop `return`).
- Explicit buttons + double enforcement: `groups=` on the button AND
  `has_group` in the method; self-approval blocked (`order.user_id ==
  env.user` raises).
- Sequential escalation in the approve method itself: manager approves →
  if max > director limit ⇒ state `director` (+ activities to the director
  group) else grant. "His manager" notified via
  `order.user_id.employee_id.parent_id.user_id` activity, with a graceful
  chatter fallback when HR has no manager.
- **Amount binding**: `sale.order.line.create/write(discount)` hook calls a
  recheck — raised above `approved_pct` ⇒ approval voided (state `none` +
  chatter note); raised above `requested_pct` while pending ⇒ chain restarts
  at manager. RPC/import safe because it lives in the model.
- Dashboard = a filtered `Discount Approvals` menu (list + badges + filters
  Waiting Manager / Waiting Director) for `group_sale_manager` — approvers see
  the actual quotations, not proxy records.

## v3 — N-tier ladder generalization (same module, verified)

The client's real org needed 4 levels (salesman / supervisor / sales manager /
company director), each with its own limit, sequential, **and a hard ceiling**
(above the top limit nothing is confirmable by anyone). The 2-tier code
generalizes cleanly by making the ladder data, not branches:

```python
DISCOUNT_TIERS = [  # (state, approver group xmlid, company limit field, label)
    ('supervisor', '...group_discount_supervisor', 'discount_supervisor_limit', 'Supervisor'),
    ('manager', '...group_discount_manager', 'discount_manager_limit', 'Sales Manager'),
    ('director', '...group_commercial_director', 'discount_director_limit', 'Company Director'),
]
# approve(): idx = states.index(current); check has_group(tiers[idx]);
#   max <= limit[idx] -> grant ; else escalate(idx+1)
# confirm(): max <= salesman_limit -> free ; max > tiers[-1] limit -> hard UserError
```

- Groups form an implied chain (director ⟹ manager ⟹ supervisor ⟹
  `sales_team.group_sale_salesman_all_leads`) so every approver can OPEN the
  quotations — an approval group without sale read access renders the buttons
  useless (record rules hide the order itself).
- One generic approve/refuse method + per-tier buttons in the view
  (`groups=` + state `invisible`), so adding a level = one tuple + one limit
  field + one button pair.
- The hard ceiling is checked in BOTH `action_confirm` and the request
  action, and defensively in approve.

## ⚠️ Pitfalls

- Whenever an approval must be **bound to a figure**, the state and the
  approved figure must live on the SAME record the figure lives on; a linked
  request model can't see the figure move.
- Keep the refusal path un-dead-ended: an explicit "Request Approval" button
  re-arms after refuse; lowering the discount below the limit confirms freely.
- The Approvals app stays the right tool for generic, human-routed requests
  with no numeric invariant (expenses-like flows) — not for amount-bound
  gates on business documents.

## Verification

Fresh-DB install, 11/11 tests: tier routing, sequential escalation,
approval-then-raise voids (the killer), raise-while-pending restarts,
refusal + re-request, AccessError per tier, no self-approval.

## Related

- `orm/amount-bound-override-authorization-for-a-hard-block.md`
- `orm/state-gated-action-button-must-be-idempotent-for-rerun.md`
- `orm/o2c-project-phase-workflow-pattern.md`
