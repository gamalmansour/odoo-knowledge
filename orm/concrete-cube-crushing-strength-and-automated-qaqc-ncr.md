# Concrete Cube Crushing Failure Lifecycle and Automated QA/QC NCR Integration

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `concrete`, `qaqc`, `ncr`, `bbs`, `crushing-test`, `sbc304`, `astm-c39`, `python311`, `f-string`, `construction`

---

## Problem

In construction ERP implementations, ready-mix concrete quality tracking presents two major failure modes:
1. **The 28-Day Decoupling Gap**: Concrete is cast on Day 1, but the contractual 28-day compressive crushing strength test occurs 4 weeks later when the work order, pouring docket, or Daily Progress Report (DPR) may already be validated, closed, or invoiced. If the cube test model is tightly coupled to mutable states on the work order, crushing test entry is blocked or fails to initiate corrective actions.
2. **Python 3.11+ SyntaxError on Escaped Quotes in f-Strings**: Attempting to inline translated strings with escaped quotes (e.g. `{_('Design f\'c:')}`) inside Python 3.11 f-string curly braces causes an immediate `SyntaxError: f-string expression part cannot include a backslash` during registry loading.
3. **Rebar BBS Rounding and Scrap Drift**: Failure to calculate theoretical cutting lengths and scrap against the standard 7.00% benchmark allows scrap costs to leak without waste tracking.

```
SyntaxError: f-string expression part cannot include a backslash
  File "construction_concrete_cube.py", line 254
    {_('Design f\'c:')} <strong>{rec.target_fc:.2f} MPa</strong>
```

## Root Cause

- In Python 3.11 (PEP 701 not backported prior to 3.12), expressions inside curly braces in f-strings cannot contain backslashes `\`. Escaped quotes like `\'` inside `_('...')` trigger a fatal `SyntaxError`.
- Without an automated integration bridge between the testing laboratory and the project's QA/QC module (`qc.ncr`), failing cube tests remain buried in lab sheets, leading to building delivery without addressing structural non-conformances under SBC 304 Section 26.12 / ASTM C39.

## Solution ✅

### 1. Decoupled Lifecycle for Cube Tests and Pour Logs
Define an independent lifecycle state machine on `construction.concrete.cube` (`draft` -> `testing` -> `pass` / `failed`) allowing lab technicians to record 7-day and 28-day breaking loads independently of whether the pour log or work order is closed.

```python
@api.depends('status_7d', 'status_28d', 'tested_count_7d', 'tested_count_28d')
def _compute_overall_result(self) -> None:
    for rec in self:
        if rec.status_28d in ('pass', 'compliant_aci'):
            rec.overall_result = 'pass'
        elif rec.status_28d == 'fail' or rec.status_7d == 'fail':
            rec.overall_result = 'failed'
        elif rec.tested_count_7d > 0 or rec.tested_count_28d > 0:
            rec.overall_result = 'testing'
        else:
            rec.overall_result = 'draft'
```

### 2. Automated Quality NCR Generation on Strength Failure
When 28-day compressive strength fails target $f'c$ (or 7-day is critically low $<50\%$), provide an automated action that creates a Critical `qc.ncr` referencing SBC 304:

```python
def action_trigger_ncr(self) -> dict:
    self.ensure_one()
    if self.ncr_id:
        raise UserError(_("An NCR (%s) is already raised for this concrete test.") % self.ncr_id.name)

    ncr_vals = {
        'project_id': self.project_id.id,
        'title': _("Concrete Compressive Strength Failure: %s - %s") % (self.pour_id.structural_element, self.pour_id.name),
        'source': 'inspection',
        'severity': 'critical',
        'sbc_clause': 'SBC 304 Section 26.12 / ASTM C39',
        'description': (
            f"Specified Target f'c: {self.target_fc:.2f} MPa\n"
            f"Achieved 28-Day Strength: {self.avg_strength_28d_mpa:.2f} MPa ({self.strength_28d_pct:.1f}% of design)\n"
            f"Immediate action required: Re-bound hammer test, UPV, or core extraction per SBC 304 Section 26.12.4."
        )
    }
    ncr = self.env['qc.ncr'].create(ncr_vals)
    self.ncr_id = ncr.id
```

### 3. Clean f-String Formatting Without Backslashes
Assign user-facing translated label strings to local variables outside the f-string block:

```python
# CORRECT:
title_fail = _('CRITICAL QUALITY NON-CONFORMANCE:')
lbl_target = _("Design Target Strength:")
rec.cube_warning_banner = f"""
<div class="alert alert-danger">
    <strong>{title_fail}</strong> {lbl_target} {rec.target_fc:.2f} MPa
</div>
"""
```

## ⚠️ Pitfalls

- **Inconsistent Store Compute Warning**: Computing stored scalar metrics (`avg_strength_28d_mpa`, `overall_result`) and non-stored HTML banners (`cube_warning_banner`) in the same `@api.depends` method triggers `UserWarning: inconsistent 'store' for computed fields` in Odoo 18. Keep scalar math and HTML alert banners in separate compute methods.
- **Unit Conversions**: Calibrated compression machines measure crushing force in **kN**. To compute strength in **MPa** ($N/mm^2$), multiply load by 1,000 before dividing by specimen area (e.g. $22,500 mm^2$ for standard 150mm cubes):
  $$\text{Strength (MPa)} = \frac{\text{Load (kN)} \times 1000}{\text{Area } (mm^2)}$$

## Verification

Run automated test suite:
```bash
python3 odoo-bin shell -c odoo.conf -d mydb --no-http << 'EOF'
import unittest
from odoo.addons.construction_concrete_bbs.tests.test_concrete_bbs import TestConcreteBbs
suite = unittest.TestLoader().loadTestsFromTestCase(TestConcreteBbs)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
EOF
```

## References
- Saudi Building Code (SBC 304 - Concrete Structures)
- ASTM C39 / ASTM C94 Standard Specifications
- Related file: `orm/modular-daily-report-aggregation-hooks-and-inconsistent-store.md`
