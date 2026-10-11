# Freezing a stored money figure across a lifecycle: snapshot own-fields + write-lock, NOT a state-guarded compute skip

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-13                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `computed-fields`, `store`, `lifecycle`, `snapshot`, `freeze`, `state-machine`, `money`, `gratuity`, `hr`

---

## Problem

A stored money figure (end-of-service gratuity, payslip net, settlement total)
must show a **live estimate while Draft** and become a **frozen snapshot** once
approved, so a later wage raise / contract edit / payroll-rule change never moves
an already-paid figure.

The tempting "freeze" is to keep the stored compute and guard it on state:

```python
# BUGGY FREEZE — looks right, silently zeroes the figure later
service_years = fields.Float(compute='_compute_service', store=True)

@api.depends('employee_id.contract_date_start', 'termination_date', 'state')
def _compute_service(self):
    for rec in self:
        if rec.state != 'draft':
            continue                     # "keep the frozen snapshot"  <-- WRONG
        rec.service_years = (rec.termination_date - rec.employee_id.contract_date_start).days / 365.0
```

Six months on, HR edits the *employee's* `contract_date_start` (a genuine data
fix). That write is a **dependency** of `service_years`, so the ORM marks the
confirmed record's `service_years` for recompute and invalidates its cache. The
compute runs, hits `continue`, and **assigns nothing** — so the stored figure
resolves to `0.0` (or raises `Compute method failed to assign`). The gratuity,
which depends on `service_years`, then recomputes downward. An approved payout
silently changes. No error, no audit trail.

## Root Cause

`if rec.state != 'draft': continue` does **not** "keep the old value". Once a
field is in the recompute set (because a dependency was written), skipping the
assignment leaves it unassigned — the ORM does **not** fall back to the stored
column. You get `False`/`0.0` or a `CacheMiss`. The skip only *appears* to work
in a same-transaction demo where no dependency ever fires after confirmation.

The deeper mistake: the frozen field still **depends on a live foreign record**
(`employee_id.contract_date_start`). Anything a computed field depends on can
move it — a lifecycle flag cannot veto that.

## Solution ✅

Freeze by **removing the live dependency**, not by guarding the compute:

1. **Snapshot the upstream value into the record's OWN plain field** at
   selection time (`create` + `onchange`), so the compute depends only on the
   record's own columns:

```python
contract_start_date = fields.Date(readonly=True, copy=False)   # plain snapshot, NOT related

@api.depends('contract_start_date', 'termination_date')        # own fields only
def _compute_service(self):
    for rec in self:
        start = rec.contract_start_date
        rec.service_years = (rec.termination_date - start).days / 365.0 \
            if start and rec.termination_date and rec.termination_date >= start else 0.0

@api.depends('service_years', 'last_wage', 'reason')           # own fields only
def _compute_gratuity_amount(self):
    for rec in self:
        rec.gratuity_amount = rec._estimate()                  # ALWAYS assigns — no skip
```

2. **Write-lock the basis fields once the record leaves Draft**, at the model
   level (view `readonly` is bypassed by RPC/import):

```python
_LOCKED = frozenset({'employee_id', 'termination_date', 'reason',
                     'last_wage', 'contract_start_date'})

def write(self, vals):
    if not self.env.context.get('allow_basis_write') and _LOCKED.intersection(vals):
        locked = self.filtered(lambda r: r.state != 'draft')
        if locked:
            raise UserError(_("Basis is locked; reset to Draft to change it."))
    return super().write(vals)
```

Now the compute is **live in Draft** (basis editable → recomputes) and **frozen
after** (basis write-locked → inputs never change → figure never moves), with no
state branch and no skipped assignment anywhere. Editing the *employee* later
touches nothing on the settlement because it holds a snapshot, not a relation.

## ⚠️ Pitfalls

- **`if state != draft: continue` in a stored compute is a false freeze.** A
  dependency write still triggers recompute; the skip yields `False`/`0.0` or
  `Compute method failed to assign`, not the previous value.
- **A frozen figure must not depend on a live foreign field.** As long as
  `contract_date_start` is `related=` / dotted in `@api.depends`, an upstream
  edit moves it. Snapshot into an own column.
- **Lock at the model, not only the view.** `readonly` in XML stops the form,
  never RPC/import/server actions. Guard `write()`.
- **Keep the compute total (always assign every record in `self`).** The whole
  bug comes from a compute path that assigns nothing.
- **Reset-to-Draft is the deliberate un-freeze.** It re-opens the basis so the
  figure recomputes on purpose — the only sanctioned way to change it.

## Verification (rolled back)

`solargy_hr` `tests/test_termination.py::test_amount_frozen_after_confirm`:
7y / wage 3000 → confirm → gratuity 13500. Then set the *employee's* wage 9000
and contract start 20y earlier, `invalidate_recordset`, re-read → **still 13500**.
`test_basis_write_locked_after_confirm`: writing `last_wage` on a confirmed
record raises `UserError`. `test_reset_to_draft_unfreezes`: reset → new wage →
figure recomputes.

## Related

- `orm/stored-compute-incomplete-depends-silent-staleness.md` (stored figure
  drifts when depends is thin — the mirror image: here we *want* a freeze)
- `orm/carry-register-across-lifecycle-stages.md` (snapshot/copy across stages)
- `orm/state-gated-action-button-must-be-idempotent-for-rerun.md` (idempotent
  workflow buttons used by the same feature)
