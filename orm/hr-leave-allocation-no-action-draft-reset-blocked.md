# hr.leave.allocation Has No `action_draft` — Reset to 'confirm' Is Explicitly Blocked

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 19 (verify on 17/18 before relying)        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `hr_holidays`, `allocation`, `state`, `action_draft`, `reset`, `workflow`

---

## Problem

> Custom bulk-allocation code implements an `action_draft()` override assuming standard
> Odoo has one (like `hr.leave` does). It does not exist on `hr.leave.allocation` in
> Odoo 19, and writing `state = 'confirm'` on a validated/refused allocation is
> explicitly rejected by `_check_approval_update`:

```
UserError: You can't reset an allocation. Cancel/delete this one and create an other
```

## Root Cause

`hr.leave.allocation` (Odoo 19, `hr_leave_allocation.py`):
- Grep for `def action_draft` → nothing. Guarding with
  `hasattr(super(), 'action_draft')` silently does nothing for standard records.
- `_check_approval_update()` maps allowed transitions via `_get_next_states_by_state()`;
  `'confirm'` is not a valid target from `validate`/`refuse`, and the error above is
  hard-coded for `state == 'confirm'` (line ~903). Any `write({'state': 'confirm'})`
  by a non-superuser raises.

## Solution ✅

- Do NOT ship a "Reset to draft" action for allocations. Follow the core philosophy:
  refuse (or delete) and create a new allocation.
- If a business flow genuinely needs re-processing, refuse the allocation
  (`action_refuse`) and `copy()` it as a fresh `confirm` record instead of mutating
  state backwards.
- Remember `_check_approval_update` starts with `if self.env.is_superuser(): return True`
  — testing as superuser/odoo-bin shell hides this blocker completely (same pitfall as
  [hr-leave-allocation-bulk-double-action-error.md](hr-leave-allocation-bulk-double-action-error.md)).

## ⚠️ Pitfalls

- `hasattr(recordset, 'action_draft')` is True the moment YOUR OWN inherit defines it —
  the check tells you nothing about core support and turns typos into silent no-ops.
- `hr.leave` (time off requests) DOES have draft/reset semantics; do not copy patterns
  from it onto `hr.leave.allocation` — the two state machines differ.

## Versions

Verified on Odoo 19.0 source.
