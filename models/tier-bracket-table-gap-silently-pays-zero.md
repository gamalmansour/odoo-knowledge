# Tier/Bracket Table With a Gap Silently Resolves to Zero Money

| Field         | Value |
|---------------|-------|
| Category      | models |
| Odoo Versions | All |
| Severity      | 🔴 Critical |
| Last Verified | 2026-08-09 |
| Author        | Gamal Mansour |

**Tags:** `commission`, `pricelist`, `tiers`, `brackets`, `policy-line`, `constraints`, `data-integrity`, `silent-zero`, `crm`, `money-integrity`

---

## Problem

Any "find the row whose range contains X" lookup — commission tiers, volume-discount
brackets, achievement bands, freight bands, bonus scales — returns an **empty recordset**
when no row covers X. Almost every implementation then treats empty as zero and continues
without complaint.

A real case: a real-estate brokerage's commission tiers for one franchise were entered as

```
  0.0% ..   4.0%   ->  4,000     <-- typo: should be 40.0
 41.0% ..  60.0%   ->  5,000
 61.0% ..  80.0%   ->  7,000
 81.0% .. 100.0%   -> 10,000
101.0% .. 120.0%   -> 12,000
121.0% .. 200.0%   -> 13,000
```

An agent at **20% achievement** matches no bracket. The commission came out **0.00** with
no error, no warning, and a fully "successful" approval:

```
personal  emp=Agent 1  pos=Property Consultant  personal=0.0  cut=0  achieved=0.0
```

The same table for a sibling company read `0.0 .. 40.0` and worked perfectly — so the bug
was invisible in testing unless you happened to test the affected company at an achievement
between 4% and 41%.

This class of defect is nasty for three reasons: it is **data, not code**, so no amount of
code review finds it; it is **silent**, so it surfaces as a payroll dispute months later;
and it is **partial**, so "it works for the other branch" masks it.

## Root Cause

The lookup is written as a domain search that is expected to match exactly one row:

```python
policy = self.env['commission.policy.line'].search([
    ('matrix_id', '=', matrix.id),
    ('from_percentage', '<=', achievement),
    ('to_percentage', '>=', achievement),
], limit=1)
return policy.commission * (unit_price / 1_000_000)   # empty recordset -> 0.0 * x -> 0.0
```

`policy` being empty is a perfectly valid recordset. `policy.commission` on an empty
recordset returns `0.0` rather than raising, so the arithmetic succeeds and the caller has
no way to distinguish "the tier says zero" from "there is no tier".

Nothing in Odoo validates that a set of range rows is contiguous or non-overlapping —
that is entirely the module author's job, and it is almost always skipped.

## Solution ✅

**1. Constrain the table so a gap cannot be saved.**

```python
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CommissionPolicyLine(models.Model):
    _inherit = "commission.policy.line"

    @api.constrains("from_percentage", "to_percentage", "matrix_id")
    def _check_bracket_coverage(self) -> None:
        """Reject tier tables that overlap or leave an uncovered range."""
        for matrix in self.mapped("matrix_id"):
            lines = self.search(
                [("matrix_id", "=", matrix.id)], order="from_percentage"
            )
            previous = None
            for line in lines:
                if line.from_percentage > line.to_percentage:
                    raise ValidationError(_(
                        "Tier %(from)s–%(to)s is inverted.",
                        **{"from": line.from_percentage, "to": line.to_percentage}
                    ))
                if previous is not None and line.from_percentage > previous:
                    raise ValidationError(_(
                        "Achievement between %(gap_from)s%% and %(gap_to)s%% is not "
                        "covered by any tier — it would silently pay zero.",
                        gap_from=previous, gap_to=line.from_percentage,
                    ))
                previous = line.to_percentage
```

Tune the contiguity test to the convention actually in use. The table above uses inclusive
integer-ish bands (`0–40` then `41–59`), so a one-unit step is legitimate and the check
should allow `line.from_percentage > previous + 1`. Half-open bands (`[from, to)`) should
require `line.from_percentage == previous` exactly. **Pick one convention and write it
down** — mixed conventions in one table are their own bug.

**2. Make the lookup refuse to be silent.**

```python
policy = self.env["commission.policy.line"].search([...], limit=1)
if not policy:
    raise UserError(_(
        "No commission tier covers an achievement of %(pct).2f%% for %(job)s. "
        "Fix the tier table before approving.",
        pct=achievement, job=matrix.job_id.name,
    ))
```

If raising is too aggressive for a batch job, log at ERROR level and skip the record —
but never let it write a zero as though it were a computed result.

**3. Audit existing data before trusting anything.**

```python
for matrix in env["commission.job.position.matrix"].search([]):
    lines = env["commission.policy.line"].search(
        [("matrix_id", "=", matrix.id)], order="from_percentage")
    prev = None
    for line in lines:
        if prev is not None and line.from_percentage > prev + 1:
            print(f"GAP  {matrix.job_id.name} / {matrix.company_id.name}: "
                  f"{prev}% .. {line.from_percentage}%")
        prev = line.to_percentage
    if lines and prev < 1000:
        print(f"OPEN-TOP  {matrix.job_id.name}: nothing above {prev}%")
```

## ⚠️ Pitfalls

- **Check the top of the range too.** A table ending at `200%` pays nothing to an
  over-achiever at 250%. Top brackets should run to a deliberately absurd ceiling.
- **A comparison table is your best detector.** The typo here was obvious only next to the
  sibling company's correct table. When several matrices should be structurally identical,
  diff them.
- **Do not assume one bad row is the only bad row.** Once you find a gap, audit every
  matrix in the database — the same person usually entered them all the same way.
- **The same trap exists anywhere ranges are looked up**: `sale.order.line` volume
  pricelist rules with `min_quantity`, delivery price rules, payroll bands, loyalty tiers.
  Only pricelists ship with sane fallback behaviour; custom tables generally do not.
- **Empty-recordset arithmetic is the underlying hazard.** `record.field * n` on an empty
  recordset returns `0.0` for every numeric field in Odoo. Any calculation that reaches for
  a `search(..., limit=1)` result without checking it can produce a silent zero.
- **Fixing the data does not retro-fix posted figures.** Anything already calculated at
  zero stays at zero until recalculated — plan the recompute alongside the data fix.

## Verification

Reproduce the zero, fix the tier, and confirm the amount changes:

```python
# before: agent at 20% achievement against a table whose first band ends at 4%
lines = env['commission.lines'].search([('lead_id', '=', LEAD_ID)])
assert lines.filtered(lambda l: l.sales_type == 'personal').personal == 0.0

env['commission.policy.line'].browse(TIER_ID).write({'to_percentage': 40.0})
tcr.write({'status': 'draft'})
tcr.action_set_approved()

lines = env['commission.lines'].search([('lead_id', '=', LEAD_ID)])
assert lines.filtered(lambda l: l.sales_type == 'personal').personal > 0.0
```

Then confirm the constraint blocks the bad data coming back:

```python
env['commission.policy.line'].browse(TIER_ID).write({'to_percentage': 4.0})
# expected: ValidationError "Achievement between 4.0% and 41.0% is not covered"
```

## References

- Related file: `models/kpi-returning-zero-for-undefined-lies-to-the-user.md` — same family
  of defect: a metric that reports zero when it means "unknown".
- Related file: `orm/undecorated-create-override-breaks-ui-creation-only.md` — another
  silent-until-production defect found in the same codebase.
