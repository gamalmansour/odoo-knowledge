# Amount-Bound Override Authorization for a Hard Workflow Block (group-approved, self-voiding)

**Category:** ORM
**Tags:** #orm, #workflow, #approval, #security, #groups, #money, #budget, #audit
**Severity:** 🟡 Medium
**Odoo Versions:** All

## Problem
A workflow step hard-blocks on a business rule (e.g. `action_complete` raises `UserError`
when a work order would exceed its budget). The business wants an **exception**: a specific
group may authorize completing anyway — but a naive "just add an `approved` boolean the
manager ticks" leaks two ways:
1. Anyone can set the boolean by ORM/import/write, bypassing the "specific group" intent.
2. The manager approves at cost 200, someone later pushes the work order to 5,000, and the
   stale approval waves it through — a blank cheque.

## Solution ✅
Model the exception as a **group-enforced action** that records *who* and *at what figure*,
plus a computed validity that self-voids when the figure grows.

```python
budget_override_approved = fields.Boolean(copy=False, tracking=True)       # the authorization
budget_override_by       = fields.Many2one('res.users', readonly=True, copy=False)
budget_override_amount   = fields.Monetary(readonly=True, copy=False)      # cost AT approval
budget_override_valid    = fields.Boolean(compute='_compute_override_valid')

@api.depends('budget_override_approved', 'budget_override_amount', 'total_cost', 'currency_id')
def _compute_override_valid(self):
    for rec in self:
        rec.budget_override_valid = bool(rec.budget_override_approved) and (
            rec.currency_id.compare_amounts(rec.total_cost, rec.budget_override_amount) <= 0)

def action_approve_budget_override(self):
    self.ensure_one()
    if not self.env.user.has_group('construction_project.group_cost_manager'):
        raise UserError(_("Only Cost Management can authorize an over-budget work order."))
    self.write({'budget_override_approved': True, 'budget_override_by': self.env.user.id,
                'budget_override_amount': self.total_cost})       # bind to the figure seen
    self.message_post(body=_("Over-budget completion authorized by %(user)s at %(amount)s.") % {...})
```

Then the block *consults the validity*, not the raw boolean, and leaves an audit note when it
waives:
```python
if projected > budget:
    if rec.budget_override_valid:
        rec.message_post(body=_("Over-budget completion authorized by %(user)s. %(detail)s") % {...})
    else:
        raise UserError(detail + _(" Blocked. A Cost Manager can authorize an exception."))
```

View: a header button `groups="…group_cost_manager"` shown only when
`is_over_budget and not budget_override_valid`, a revoke button when approved, and a
warning/authorized banner. `copy=False` on all three stored fields so a duplicated record
starts unauthorized.

## ⚠️ Pitfalls
- **Bind the authorization to the amount, gate on the computed `_valid`, never the raw
  boolean.** Storing `budget_override_amount = total_cost` at approval and checking
  `total_cost <= that` is what stops the "approve small, complete big" loophole — the
  authorization voids itself and the button reappears for re-approval.
- **Enforce the group in the ACTION, and make it the first line** (before any write), exactly
  like the existing `action_approve_cost_line`. `has_group` returns True for the superuser,
  so a `TransactionCase` running as root won't exercise the negative path — test it with
  `record.with_user(non_manager)` where the user lacks the group (give them a sibling
  construction group so it's the group check, not an AccessError, that fires).
- **New fields default empty ⇒ no migration, no behavior change** for existing records: with
  no authorization the block behaves exactly as before. Verify post-upgrade that existing
  rows have `override_approved = False`.
- **Use `currency.compare_amounts` (not `<=` on floats)** for the validity check so rounding
  noise doesn't spuriously void or honor an authorization.
- **Leave an audit trail:** post to the chatter *both* on authorization (who + amount) and on
  the waived completion (who authorized + what was exceeded) — a silent bypass of a financial
  control is a review finding waiting to happen.

## Related
- `views/header-cascade-subitem-drives-line-cost-target.md` — the same `action_complete`
  gate stack; adding gates there is what makes the "test passes for the wrong reason" pitfall
  bite.
- The in-repo sibling pattern: `project.material.issue.action_approve_cost_line` /
  `needs_cost_approval` (out-of-plan cost-line approval) — same group, non-amount-bound.
