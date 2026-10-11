# HSE Method Statements (SWMS) Empty Screen, Approval Deadlock, & Risk Assessment Coupling

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `method-statement`, `swms`, `approval-mixin`, `deadlock`, `risk-assessment`, `smart-button`

---

## Problem

When navigating to **Safety > Planning & Approvals > Method Statements** (`action_hse_method_statement`):
1. **Empty Screen:** The list view is completely empty because zero demo or seed records existed in the module for `hse.method.statement`.
2. **Approval Workflow Deadlock:** `hse.method.statement` inherits `approval.mixin`. When no dynamic approval chain is configured, `approval_status` remains `'none'`. Upon submitting (`action_submit()`), `ms_state` transitions to `'submitted'`. However, the form header only exposed approval buttons when `approval_status == 'in_progress'` (`invisible="approval_status != 'in_progress'"`). Consequently, submitted method statements were permanently stuck in a deadlock where no user could ever approve or reject them.
3. **Decoupled Risk Assessment & SWMS Details:** Safe Work Method Statements (SWMS) lacked essential operational fields (scope of work, detailed methodology, plant & equipment, safety controls, emergency response, and document revisions), and lacked bidirectional smart stat buttons linking to `hse.risk.assessment`.

---

## Root Cause

1. **Missing Data in XML:** `demo_hse_extras.xml` seeded TBTs, training sessions, and PPE, but contained zero entries for `hse.method.statement`.
2. **Dual-Workflow Mismatch:** `approval.mixin` manages multi-stage approval chains. When no chain rule matches, `approval_status` stays `'none'`, but the model's `_compute_ms_state` and views did not provide fallback direct approval actions for HSE Managers.
3. **Shallow Data Model:** The original model only had `title`, `project_id`, `attachment_ids`, and `risk_assessment_id`, missing standard ISO 45001 / OSHA SWMS sections.

---

## Solution ✅

### 1. Resolve Approval Deadlock & Add SWMS Logic in `hse_method_statement.py`

Provide fallback direct approval by HSE Managers that delegates to the approval chain if active, or directly approves if no chain is configured:

```python
class HseMethodStatement(models.Model):
    _name = 'hse.method.statement'
    _description = 'HSE Method Statement (SWMS)'
    _inherit = ['approval.mixin', 'hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    # Standard SWMS Fields
    revision = fields.Char(string='Revision', default='R0', tracking=True)
    prepared_by_id = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user, tracking=True)
    date_prepared = fields.Date(string='Date Prepared', default=fields.Date.context_today, tracking=True)
    scope_of_work = fields.Html(string='Scope of Work')
    methodology = fields.Html(string='Methodology & Work Procedure')
    equipment_and_tools = fields.Text(string='Plant & Equipment')
    safety_measures = fields.Text(string='Safety & Environmental Controls')
    emergency_procedures = fields.Text(string='Emergency Response')

    def action_submit(self) -> None:
        """Submit the method statement for approval."""
        for rec in self:
            if not rec.title:
                raise ValidationError(_("A descriptive title is required before submitting."))
            rec.action_start_approval()
            if rec.approval_status == 'none':
                rec.ms_state = 'submitted'

    def action_approve(self) -> None:
        """Direct approve or delegate to approval chain."""
        for rec in self:
            if rec.approval_status == 'in_progress':
                rec.action_approve_current()
            else:
                rec.ms_state = 'approved'

    def action_reject(self) -> None:
        """Direct reject or delegate to approval chain."""
        for rec in self:
            if rec.approval_status == 'in_progress':
                rec.action_reject_current()
            else:
                rec.ms_state = 'rejected'

    def action_reset_draft(self) -> None:
        for rec in self:
            if rec.ms_state == 'approved' and not self.env.user.has_group('construction_hse.group_hse_manager'):
                raise UserError(_("Only HSE Managers can reset an approved method statement to draft."))
            rec.ms_state = 'draft'

    def action_view_risk_assessment(self) -> dict:
        self.ensure_one()
        if not self.risk_assessment_id:
            return {}
        return {
            'type': 'ir.actions.act_window',
            'name': _('Linked Risk Assessment'),
            'res_model': 'hse.risk.assessment',
            'res_id': self.risk_assessment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
```

### 2. View Header & Smart Buttons in `hse_method_statement_views.xml`

```xml
<header>
    <button name="action_submit" type="object" string="Submit for Approval" invisible="ms_state != 'draft'" class="oe_highlight"/>
    <button name="action_approve" type="object" string="Approve" invisible="ms_state != 'submitted'" class="oe_highlight" groups="construction_hse.group_hse_manager"/>
    <button name="action_reject" type="object" string="Reject" invisible="ms_state != 'submitted'" groups="construction_hse.group_hse_manager"/>
    <button name="action_reset_draft" type="object" string="Reset to Draft" invisible="ms_state not in ('rejected', 'approved')"/>
    <field name="ms_state" widget="statusbar" statusbar_visible="draft,submitted,approved"/>
</header>
```

---

## ⚠️ Pitfalls

1. **`approval.mixin` State Inconsistency:**
   When using `approval.mixin`, always verify what happens when `approval_status == 'none'`. If approval buttons are gated exclusively by `approval_status == 'in_progress'`, users without an approval chain configured will be permanently locked out from approving records.
2. **Bidirectional Foreign Keys:**
   When two models (`hse.method.statement` and `hse.risk.assessment`) reference each other via Many2one fields, ensure assigning one automatically updates the inverse in `create()` or `write()`.

---

## Verification

In Odoo Shell:
```python
ms_list = env['hse.method.statement'].search([])
for m in ms_list:
    print(m.name, m.title, m.project_id.name, m.ms_state, m.risk_assessment_id.name)
```
Ensure all method statements appear with populated SWMS sections, valid status progression, and linked risk assessments.
