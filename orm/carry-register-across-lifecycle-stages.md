# Carrying a Register Across Lifecycle Stages (Tender → Project) With Scale Mapping

**Category:** ORM
**Tags:** #orm, #create-override, #cross-module, #selection, #mapping, #construction, #risk
**Severity:** 🟡 Medium
**Last Verified:** 2026-07-08
**Odoo Versions:** 17

## Problem
A suite tracks the "same" concept in two decoupled modules with different
models and different field scales — e.g. a tender risk register
(`tender.risk.line`, 1-3 probability/impact, small category set) and a project
risk register (`construction.risk`, 1-5 scale, richer categories + residual +
response). Users expect risks to carry from tender to project the way the BOQ
does, but there is no copy logic, so they re-enter everything by hand.

## Solution ✅
Put the carry-over in the module that sees BOTH models. Here `construction_risk`
depends on `construction_project`, which transitively pulls
`construction_contract` → `construction_tender`, so the tender register is
reachable at runtime via the relation chain `project.contract_id.tender_id.
risk_line_ids` — **no new manifest dependency is required** (the relation is
resolved by the ORM and the models are guaranteed loaded by the transitive
depends).

Hook the copy into `construction.project.create()` so it fires for every
creation path (the create-project wizard AND the contract's `action_activate`,
both of which ultimately `create()` the project):

```python
@api.model_create_multi
def create(self, vals_list):
    projects = super().create(vals_list)
    if not self.env.context.get('skip_tender_risk_copy'):
        for project in projects:
            project._copy_risks_from_tender()
    return projects
```

`_copy_risks_from_tender` no-ops when the project already has risks or the
tender has none (idempotent), skips `display_type` section/note rows, and maps
the divergent fields explicitly:

- **Scale 1-3 → 1-5:** `{'1':'1','2':'3','3':'5'}` (spread, don't clip to 1-3).
- **Category set → richer set:** explicit dict, fall back to `'other'`.
- **Status:** `mitigated → mitigating`, etc.
- **Text → required Char name:** first line, truncated (`raw.splitlines()[0][:120]`),
  full text into the `description`; provide a fallback title if blank.
- Only set `owner_id` when the source `responsible_id` is set, so the target's
  `default=env.user` still applies otherwise.

## ⚠️ Pitfalls
- Don't clip the 1-3 values into the low end of the 1-5 matrix (1,2,3) — a
  tender "High/Major" (3) should land on the project's "Almost Certain/Severe"
  (5), otherwise every carried risk looks trivial.
- The target `name` is a required `Char`; the source is a multi-line `Text`.
  Passing the raw Text can exceed sane title length and looks wrong in list
  views — split + truncate, keep the full text in `description`.
- Guard with a context flag (`skip_tender_risk_copy`) so bulk/demo/data loads
  can opt out.
- Idempotency: key the no-op on `self.risk_ids` so a re-run never duplicates.

## Verification (rolled back)
Tender with a section + 2 risks (contractual/3×2/mitigated/owner,
supply_chain/2×3/open) → project via wizard → exactly 2 project risks:
category commercial & procurement, probability 5 & 3, impact 3 & 5, costs
50k/80k carried, statuses mitigating/open, multi-line title trimmed to its
first line, and the Risks smart button count = 2.

## Related
- `one2many_import_boq.md`, `polymorphic-billing-method-per-contract-type.md`
