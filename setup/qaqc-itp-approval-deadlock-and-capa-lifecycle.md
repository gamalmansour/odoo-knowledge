# QA/QC Inspection & Test Plans (ITP) Approval Deadlock, Empty Screen, & CAPA Lifecycle

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `qaqc`, `quality`, `itp`, `approval-mixin`, `deadlock`, `capa`, `corrective-actions`, `ncr`, `inspection-request`

---

## Problem

When navigating to **Quality (QA/QC) > Quality Control > Inspection & Test Plans** (`action_qc_itp`) or **Corrective Actions** (`action_qc_corrective_action`):

1. **Empty Screens:** Both screens displayed zero records in a clean or freshly restored database (`hadhoud_demo`), leaving quality managers without foundational inspection plans or non-conformance remediation workflows.
2. **Approval Workflow Deadlock in `qc.itp`:**
   - `qc.itp` inherits `approval.mixin`.
   - When company setting `qc_require_itp_approval` is enabled (`True`), `action_submit()` executes `rec.action_start_approval()`.
   - If no dynamic approval chain (`approval.tier` / `approval.stage`) is configured for model `qc.itp`, `approval_status` remains `'none'`.
   - The form view (`qc_itp_views.xml`) only reveals the "Approve" and "Reject" buttons when `approval_status == 'in_progress'` (`invisible="approval_status != 'in_progress'"`).
   - Because `approval_status` is `'none'`, the Approve and Reject buttons remain completely invisible, while `state` remains trapped in `'draft'`. Clicking "Submit" again just repeats the cycle, permanently locking the ITP in a draft state deadlock!
3. **Decoupled Inspection Requests & NCR Remediations:**
   - Work Inspection Requests (WIR) and Material Inspection Requests (MIR) require approved ITPs and specific activity lines (`itp_line_id`) to govern Hold and Witness points on site.
   - Non-Conformance Reports (NCRs) that were closed or under review lacked formal Corrective and Preventive Actions (CAPA) with assigned responsibilities, deadlines, and closure verification.

---

## Root Cause

1. **Missing Seed / Demo Data:** `demo_itp.xml` was either omitted or bypassed during installation without demo data, leaving both `qc.itp` and `qc.corrective.action` completely unpopulated.
2. **Approval Engine Misalignment:** `approval.mixin` manages multi-stage approval hierarchies. When no dynamic stages match the document, it sets `approval_status = 'none'`. However, `_compute_state()` only transitions to `'approved'` if `approval_status == 'approved'`, and the view did not provide a fallback direct approval action for Quality Managers (`group_qc_manager`).
3. **Field Polymorphism in CAPA:** `qc.corrective.action` uses both `ncr_id` (`Many2one`) and `source_ref` (`Reference`), which must be properly populated together so that both the direct NCR form (`action_ids`) and generic source references correctly display the action.

---

## Solution ✅

### 1. Fix Approval Deadlock in `construction_qaqc/models/qc_itp.py`

Implement fallback auto-approval in `action_submit()` when no dynamic approval tiers are configured, and provide explicit direct approval / reset actions for QC Managers:

```python
    def action_submit(self) -> None:
        """Submit the ITP for approval. If no approval chain is configured, fallback to auto-approval."""
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("You cannot submit an ITP without lines."))
                
            if rec.company_id.qc_require_itp_approval:
                rec.action_start_approval()
                # If no dynamic approval chain was configured, approval_status remains 'none'.
                # Fallback to direct approved to prevent deadlock in draft state with invisible approve buttons.
                if rec.approval_status == 'none':
                    rec.approval_status = 'approved'
            else:
                rec.approval_status = 'approved'

    def action_approve(self) -> None:
        """Direct approve by QC Manager or advance approval chain."""
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("You cannot approve an ITP without inspection lines."))
            if rec.approval_status == 'in_progress':
                rec.action_approve_current()
            else:
                rec.approval_status = 'approved'

    def action_reject(self) -> None:
        """Direct reject or reject current approval stage."""
        for rec in self:
            if rec.approval_status == 'in_progress':
                rec.action_reject_current()
            else:
                rec.approval_status = 'rejected'

    def action_reset_draft(self) -> None:
        """Reset ITP to draft."""
        for rec in self:
            if rec.state == 'superseded':
                raise UserError(_("You cannot reset a superseded ITP to draft."))
            rec.approval_status = 'none'
```

### 2. Update Form Header in `construction_qaqc/views/qc_itp_views.xml`

Expose the direct approve button to Quality Managers and allow resetting to draft:

```xml
<header>
    <button name="action_submit" string="Submit" type="object" class="oe_highlight" invisible="state != 'draft'"/>
    
    <!-- Direct Approve Button for QC Manager if draft and no approval chain in progress -->
    <button name="action_approve" type="object" string="Direct Approve" class="btn-success" groups="construction_qaqc.group_qc_manager" invisible="state != 'draft' or approval_status == 'in_progress'"/>
    
    <!-- Approval Mixin Buttons - Standard Integration -->
    <button name="action_approve_current" type="object" string="Approve" class="btn-success" invisible="approval_status != 'in_progress'"/>
    <button name="action_reject_current" type="object" string="Reject" class="btn-danger" invisible="approval_status != 'in_progress'"/>
    
    <button name="action_reset_draft" string="Reset to Draft" type="object" invisible="state == 'draft' or state == 'superseded'"/>
    <button name="action_create_revision" string="Create Revision" type="object" invisible="state != 'approved'"/>
    
    <field name="state" widget="statusbar" statusbar_visible="draft,approved,superseded"/>
</header>
```

### 3. Seed Multi-Discipline ITPs & Realistic CAPAs

Populate:
- **Structural ITP (Rafah):** Reinforced Concrete Foundations & Columns with 5 inspection activities (Hold, Witness, Review, Surveillance).
- **Civil ITP (Dahab):** Marine Rip-Rap & Wave Breakers with Geotextile and Precast Accropode armor unit testing.
- **Structural Steel ITP (Ismailia):** Fabrication, Ultrasonic NDT testing, high-strength bolt torque, and fireproofing DFT.
- **Electrical ITP (Monorail):** Cable trays, earth resistance (< 1 Ohm), and insulation megger testing.
- **5 CAPAs:** Linked to `NCR/26/00001` and `NCR/26/00003` covering corrective grouting, preventive rebar vibration guidelines, containment quarantining of non-PVC tie wires, and torque wrench calibration.

---

## ⚠️ Pitfalls

1. **Single Approved ITP Constraint:** `qc.itp` enforces `_check_single_approved_itp` (`@api.constrains('state', 'project_id', 'discipline', 'title')`). Never approve two ITPs with the exact same Title and Discipline on the same Project without superseding the previous revision (`action_create_revision()`).
2. **Computed State Traps:** `state` in `qc.itp` is computed from `approval_status`. Writing directly to `state` via ORM write without setting `approval_status = 'approved'` will cause Odoo's compute engine to revert `state` to `'draft'`.
3. **Activity Notifications on CAPA:** When creating `qc.corrective.action`, assigning `responsible_id` automatically triggers `record.activity_schedule('mail.mail_activity_data_todo')`. Calling `action_done()` automatically resolves these activities.

---

## Verification

```bash
# 1. Verify ITPs and Approval States
python -c "
import odoo
from odoo import api, SUPERUSER_ID
odoo.tools.config.parse_config(['-c', '/Users/gamal/odoo/odoo18.0/odoo18_con.conf', '-d', 'hadhoud_demo'])
with odoo.registry('hadhoud_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    for itp in env['qc.itp'].search([]):
        print(itp.name, itp.discipline, itp.state, len(itp.line_ids))
"

# 2. Verify Corrective Actions (CAPAs) and Linked NCRs
python -c "
import odoo
from odoo import api, SUPERUSER_ID
odoo.tools.config.parse_config(['-c', '/Users/gamal/odoo/odoo18.0/odoo18_con.conf', '-d', 'hadhoud_demo'])
with odoo.registry('hadhoud_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    for c in env['qc.corrective.action'].search([]):
        print(c.name, c.action_type, c.state, c.ncr_id.name if c.ncr_id else None)
"
```

## References

- Related: `setup/hse-method-statements-approval-deadlock-and-swms.md`
- Related: `setup/construction-seeding-field-pitfalls-dcc-qc-claims.md`
- Module: `construction_qaqc`
