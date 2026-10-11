# Adding a new state to a Selection silently breaks every `!= done` guard

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-14                                 |
| Author        | Gamal Mansour                              |

**Tags:** `orm`, `state-machine`, `selection`, `control-flow`, `workflow`, `counters`

---

## Problem

> You add a new state to a `Selection` state field (e.g. a `cancelled` visit
> state next to `draft`/`in_progress`/`done`). Everything compiles and the happy
> path works, but existing logic written as `state != 'done'` or
> `state not in ('draft', 'in_progress', 'done')` now treats the new state
> **wrong** — a cancelled record keeps blocking a sequence, keeps counting as
> pending, or never gets excluded from a rollup.

Concrete case: a day's visits must be done in order, enforced by a predecessor
check `if predecessor.state != 'done': block`. After adding `cancelled`, a
**skipped** visit (`state == 'cancelled'`) still counted as "not done" and
blocked every later visit in the day — the rep was stuck.

## Root Cause

Boolean guards were written against the *closed set of states that existed at
the time*. `state != 'done'` really meant "not finished" — but "finished" now
has two members (`done` and `cancelled`), and the guard only knows one. Adding a
Selection value is not a local change: it changes the truth of every existing
comparison that partitioned records by state.

## Solution ✅

> Before shipping a new state, grep every reference to the field and re-classify
> each check against the **new** partition. Prefer positive membership tests
> (`state in ('open', 'in_progress')`) over negative ones (`state != 'done'`) so
> a future state doesn't silently fall on the wrong side.

```bash
grep -rnE "\.state *(==|!=|not +in|in) " custom/<module>/  # audit EVERY hit
```

```python
# before (assumed done was the only terminal state)
if predecessor.state != 'done':
    block()

# after (terminal = done OR cancelled)
if predecessor.state not in ('done', 'cancelled'):
    block()
```

Also re-check: "pending" counters/badges, calendar/list domains, rollups and
computes, `web_ribbon`/statusbar visibility, and report filters.

## ⚠️ Pitfalls

- The bug is invisible on the happy path and in a fresh DB — it only shows once a
  record actually reaches the new state. Add a test that drives a record *into*
  the new state and then exercises the dependent logic (sequence, counts).
- `statusbar_visible` and badge `decoration-*` must be updated too, or the new
  state renders blank/uncoloured in the UI.
- A negative guard (`!= 'done'`) is the usual culprit; search for those first.

## Verification

```python
# a cancelled predecessor must NOT block the next visit
v1.action_skip_visit(reason.id)          # v1 -> cancelled
self.assertFalse(self._get_blocking_predecessor_visit(v2))
```

## References

- Related file: `orm/onchange-only-computation-breaks-nonform-create.md`
- Related file: `views/portal-workflow-rule-viewer-bypass.md`
