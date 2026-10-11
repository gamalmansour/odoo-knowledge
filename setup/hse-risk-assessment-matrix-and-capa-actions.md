# HSE Risk Assessments Empty Screen, 5x5 Matrix Boundaries, & CAPA Action Linkage

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `risk-assessment`, `matrix`, `capa`, `demo-data`, `smart-button`

---

## Problem

When navigating to **Safety > Planning & Approvals > Risk Assessments** (`action_hse_risk_assessment`), the list view is completely empty:
1. No records appear in the list view.
2. In `hse.risk.assessment`, hazard lines (`hse.risk.line`) can generate CAPA actions via `action_create_action()`. However, the parent Risk Assessment had no visibility (no smart button, no count) into these generated CAPA actions, making cross-audit impossible without manual database checks.
3. Workflow guardrails were absent: a user could transition an assessment to `assessed` or `approved` with zero risk lines.
4. The search view lacked filters for workflow status (`draft`, `assessed`, `approved`) and group-by filters for `Assessor` and `Assessment Date: Month`.

---

## Root Cause

1. **Manifest Demo Data Boundary:**
   Risk assessment records were defined only inside the module's demo XML data under `__manifest__.py`. In clean or pre-sales environments installed without demo data, the model `hse.risk.assessment` remains empty.
2. **Missing Bidirectional Navigation:**
   Each `hse.risk.line` has an optional `action_id` (Many2one `hse.action`), but the parent `hse.risk.assessment` lacked computed fields (`action_ids`, `action_count`) and a `button_box` smart button to inspect and navigate to all actions generated from its lines.
3. **Missing State Validation:**
   `action_mark_assessed()` lacked validation ensuring `len(self.line_ids) > 0`, allowing empty assessments to be approved.

---

## Solution ✅

### 1. Model Enhancements in `hse_risk_assessment.py`

Add computed `action_ids`, `action_count`, smart button action, and workflow safeguards:

```python
class HseRiskAssessment(models.Model):
    _name = 'hse.risk.assessment'
    _description = 'HSE Risk Assessment'
    _inherit = ['hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    action_ids = fields.Many2many(
        'hse.action',
        string='CAPA Actions',
        compute='_compute_action_ids',
        help="All corrective and preventive actions spawned from this risk assessment's lines."
    )
    action_count = fields.Integer(
        string='Action Count',
        compute='_compute_action_ids',
        help="Number of linked CAPA actions."
    )

    @api.depends('line_ids.action_id')
    def _compute_action_ids(self) -> None:
        for assessment in self:
            actions = assessment.line_ids.mapped('action_id')
            assessment.action_ids = actions
            assessment.action_count = len(actions)

    def action_view_actions(self) -> dict:
        """Navigate to linked CAPA actions from smart button."""
        self.ensure_one()
        actions = self.action_ids
        action_data = {
            'name': _('CAPA Actions'),
            'type': 'ir.actions.act_window',
            'res_model': 'hse.action',
            'domain': [('id', 'in', actions.ids)],
        }
        if len(actions) == 1:
            action_data.update({
                'view_mode': 'form',
                'res_id': actions.id,
            })
        else:
            action_data.update({
                'view_mode': 'list,form',
            })
        return action_data

    def action_mark_assessed(self) -> None:
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("You cannot assess a risk assessment without adding at least one risk line."))
            rec.state = 'assessed'

    def action_reset_draft(self) -> None:
        for rec in self:
            if rec.state == 'approved' and not self.env.user.has_group('construction_hse.group_hse_manager'):
                raise UserError(_("Only HSE Managers can reset an approved risk assessment to draft."))
            rec.state = 'draft'
```

### 2. View Enhancements in `hse_risk_assessment_views.xml`

Add `oe_button_box` to form view and filters to search view:

```xml
<!-- Form View Smart Button -->
<sheet>
    <div class="oe_button_box" name="button_box">
        <button name="action_view_actions" type="object"
                class="oe_stat_button" icon="fa-tasks"
                invisible="action_count == 0">
            <field name="action_count" widget="statinfo" string="CAPA Actions"/>
        </button>
    </div>
    ...
</sheet>

<!-- Search View Filters -->
<search string="Search Risk Assessments">
    <field name="name"/>
    <field name="project_id"/>
    <field name="assessor_id"/>
    <field name="activity_desc"/>
    <separator/>
    <filter string="Draft" name="draft" domain="[('state', '=', 'draft')]"/>
    <filter string="Assessed" name="assessed" domain="[('state', '=', 'assessed')]"/>
    <filter string="Approved" name="approved" domain="[('state', '=', 'approved')]"/>
    <separator/>
    <group expand="0" string="Group By">
        <filter string="Project" name="group_project" context="{'group_by': 'project_id'}"/>
        <filter string="Assessor" name="group_assessor" context="{'group_by': 'assessor_id'}"/>
        <filter string="Overall Risk" name="group_risk" context="{'group_by': 'overall_risk_level'}"/>
        <filter string="Status" name="group_state" context="{'group_by': 'state'}"/>
        <filter string="Assessment Date" name="group_date" context="{'group_by': 'assessment_date:month'}"/>
    </group>
</search>
```

---

## ⚠️ Pitfalls

1. **One2many Dependent Recomputation:**
   When defining computed fields based on grandchild relations (`line_ids.action_id`), always use `@api.depends('line_ids.action_id')` so that when a user creates an action from a line, the parent assessment immediately increments its `action_count`.
2. **Smart Button UX:**
   If `action_count == 1`, navigate directly to `view_mode='form'` with `res_id`. If `> 1`, navigate to `list,form`.
3. **Workflow Integrity:**
   Never allow risk assessments to transition to assessed/approved without at least one hazard analysis line (`ValidationError`).

---

## Verification

Run Odoo Shell:
```python
assessments = env['hse.risk.assessment'].search([])
for a in assessments:
    print(a.name, a.project_id.name, a.overall_risk_level, a.state, a.action_count)
```
Confirm all seeded assessments load with accurate residual scores and linked CAPA action counts.
