# Two Independent Control Policies Collapsed Into One Guard (Silent Shadowing)

**Category:** ORM
**Tags:** #orm, #validation, #policy, #guard, #construction, #requisition, #business-logic
**Severity:** 🟡 Medium
**Last Verified:** 2026-07-08
**Odoo Versions:** 17

## Problem
A model exposes TWO independent control policies (here on `construction.profile`:
`qty_control_policy` and `budget_control_policy`, each off/warn/block) that are
meant to gate two different things (over-quantity vs over-budget). A guard was
written reading only ONE of them and using it to gate BOTH conditions:

```python
# BAD — over-qty AND over-budget both gated by the budget policy
policy = req._budget_policy()
if policy == 'off':
    return
over = lines.filtered(lambda l: l.is_over_qty or l.is_over_budget)
...
```

Result: setting `budget_control_policy = 'off'` **silently disabled the quantity
check too**, even when `qty_control_policy = 'block'`. The quantity policy the
user configured was never consulted on this flow — a config that appears active
in the UI but does nothing (worst kind of control gap: false sense of safety).

Observed in the material-requisition approval guard while the work-order flow
(a sibling enforcement point) correctly kept the two policies separate — so the
same two settings behaved differently in two places.

## Solution ✅
Resolve each policy separately and gate its own condition, then combine the
outcomes (block wins over warn; surface all messages):

```python
qty_policy    = req._qty_policy()
budget_policy = req._budget_policy()
over_qty    = lines.filtered('is_over_qty')
over_budget = lines.filtered('is_over_budget')

block_details, warn_details = [], []
if over_qty and qty_policy != 'off':
    (block_details if qty_policy == 'block' else warn_details).extend(qty_msgs)
if over_budget and budget_policy != 'off':
    (block_details if budget_policy == 'block' else warn_details).extend(budget_msgs)

if block_details:
    raise UserError(header + "\n".join(block_details + warn_details))
if warn_details:
    req.message_post(body=header + "\n".join(warn_details))
```

## ⚠️ Pitfalls
- When the SAME two settings are enforced in more than one place (work order +
  requisition here), audit ALL enforcement points — fixing one leaves the other
  inconsistent, and users hit different behavior depending on the door they
  entered.
- A line can trip BOTH conditions; keep the messages separate so "block wins"
  still shows the warn-level findings for context.
- Don't early-`return`/`continue` on one policy being `off` — that is exactly
  what shadows the other policy.

## Verification (rolled back)
Profile qty=block/budget=off with an over-qty (not over-budget) requisition line
now **blocks** (previously allowed); qty=warn/budget=off warns; qty=off/budget=off
ignores; budget-over lines still governed independently by the budget policy.
