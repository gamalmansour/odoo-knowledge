# A Dotted Domain Applies the Comodel's Record Rules — and Quietly Empties the Result

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `ir.rule`, `domain`, `many2one`, `search`, `silent-failure`, `sudo`, `record-rules`

---

## Problem

A search whose domain traverses a many2one:

```python
lines = self.env['medical.cycle.plan.line'].search([
    ('rep_id', '=', employee.id),
    ('cycle_id.status', '=', 'active'),   # <-- the trap
])
```

works perfectly for the admin and returns **empty** for the restricted user —
with no error, no log line, nothing. In our case the rep's "My Day" screen
and day-payload API returned zero plan lines whenever the rep's territory
linkage wasn't configured, even though the MR record rule on the *lines*
matched them all.

## Root Cause

Evaluating `cycle_id.status` builds a subquery on the comodel
(`medical.territory.cycle`) — and that subquery is filtered by the CALLER's
record rules on the comodel. The MR's cycle rule was
`[('territory_ids.rep_ids', 'in', [user.employee_id.id])]`; with no
territory→rep link, the user could see no cycles, so the subquery returned
no ids, so the *line* search matched nothing. The line-level rule was
irrelevant: the traversal died one model earlier.

The failure is invisible in tests that run as admin/superuser — it only
appears under `with_user()` with a genuinely restricted account.

## Solution ✅

When the traversed model is only a *qualifier* (which cycles are active),
resolve its ids as superuser and keep the main model's security intact:

```python
def _active_cycle_ids(self):
    """Only ids leak here; the plan LINES stay filtered by their own rules."""
    return self.env['medical.territory.cycle'].sudo().search(
        [('status', '=', 'active')]).ids

lines = self.env['medical.cycle.plan.line'].search([
    ('rep_id', '=', employee.id),
    ('cycle_id', 'in', self._active_cycle_ids()),
])
```

This is a deliberate security decision — document it at the helper: the ids
of active cycles are not sensitive; the records the user actually reads are
still rule-filtered.

## ⚠️ Pitfalls

- Every dotted domain in code that runs as a restricted user is a suspect:
  `('partner_id.category_id', ...)`, `('order_id.state', ...)` — audit them
  when a screen is "randomly empty for some users".
- Do NOT fix it by widening the comodel's record rule — you would be granting
  read access to whole records to repair an id lookup.
- Tests must drive these paths **with_user()** (KB:
  env-su-guard-silently-passes-in-transactioncase); an admin-run test cannot
  catch this class at all.

## Verification

```python
payload_admin = Model.get_day_payload()                      # as admin
payload_rep = Model.with_user(rep_user).get_day_payload()    # as MR
assert payload_rep['behind_plan'], "restricted user must see their own lines"
```

## References

- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `orm/non-stored-field-in-search-domain-is-silently-dropped.md` —
  the sibling silent-domain failure.
