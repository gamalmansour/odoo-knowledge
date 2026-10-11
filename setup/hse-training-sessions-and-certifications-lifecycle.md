# HSE Training Courses, Sessions, & Certifications Lifecycle & Sequence

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `training`, `sessions`, `certifications`, `sequence`, `smart-button`, `relativedelta`

---

## Problem

When navigating to **Safety > Training > Courses, Sessions, or Certifications**:
1. **Empty Screens:** All three views were completely empty in clean or demo installations.
2. **Missing Certification Sequence & Name:** `hse.certification` had no sequence defined in `ir_sequence_data.xml` and lacked a primary `name` field, causing records to lack proper referencing and display names in relational dropdowns.
3. **Audit Traceability Break:** Certifications were created with `employee_id` and `course_id`, but omitted `session_id`. In an ISO 45001 / OSHA audit, the organization could not prove which specific site session, trainer, or date a worker attended to earn their qualification.
4. **Calendar Expiry Drift:** Calculating certification expiration via `days = validity_months * 30` caused expiry dates to drift by up to 5-10 days over multi-year validity periods compared to true calendar months.
5. **No Smart Button Navigation:** No stat buttons connected Courses to their Sessions, or Sessions to their issued Certifications.

---

## Root Cause

1. Data files lacked seed records for courses, sessions, and certifications.
2. `hse.certification` lacked a dedicated sequence and `session_id` Many2one back-reference.
3. Using integer days approximation instead of `relativedelta(months=...)`.

---

## Solution ✅

### 1. Model Enhancements in `hse_training.py`

Add sequences, bidirectional smart buttons, and exact calendar expiry:

```python
from dateutil.relativedelta import relativedelta

class HseTrainingCourse(models.Model):
    _name = 'hse.training.course'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string='Course Code', tracking=True)
    session_ids = fields.One2many('hse.training.session', 'course_id', string='Sessions')
    session_count = fields.Integer(compute='_compute_counts')
    certification_ids = fields.One2many('hse.certification', 'course_id', string='Certifications')
    certification_count = fields.Integer(compute='_compute_counts')

    @api.depends('session_ids', 'certification_ids')
    def _compute_counts(self) -> None:
        for rec in self:
            rec.session_count = len(rec.session_ids)
            rec.certification_count = len(rec.certification_ids)


class HseTrainingSession(models.Model):
    _name = 'hse.training.session'
    _inherit = ['hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    certification_ids = fields.One2many('hse.certification', 'session_id', string='Issued Certifications')
    certification_count = fields.Integer(compute='_compute_certification_count')

    def action_done(self) -> None:
        for rec in self:
            if not rec.attendee_line_ids:
                raise ValidationError(_("You cannot complete a training session without adding at least one attendee."))
            rec.state = 'done'
            for line in rec.attendee_line_ids:
                if line.result == 'pass' and not line.certification_id:
                    cert = self.env['hse.certification'].create({
                        'employee_id': line.employee_id.id,
                        'course_id': rec.course_id.id,
                        'session_id': rec.id,
                        'issue_date': rec.session_date,
                    })
                    line.certification_id = cert.id


class HseCertification(models.Model):
    _name = 'hse.certification'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Certificate Number', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    session_id = fields.Many2one('hse.training.session', string='Training Session', tracking=True)
    project_id = fields.Many2one('construction.project', string='Project', related='session_id.project_id', store=True)

    @api.depends('issue_date', 'course_id.validity_months')
    def _compute_expiry(self) -> None:
        for rec in self:
            if rec.issue_date and rec.course_id.validity_months:
                rec.expiry_date = rec.issue_date + relativedelta(months=rec.course_id.validity_months)
            else:
                rec.expiry_date = False
```

### 2. Sequence in `ir_sequence_data.xml`

```xml
<record id="seq_hse_certification" model="ir.sequence">
    <field name="name">HSE Certification</field>
    <field name="code">hse.certification</field>
    <field name="prefix">CERT/</field>
    <field name="padding">5</field>
    <field name="company_id" eval="False"/>
</record>
```

---

## ⚠️ Pitfalls

1. **`relativedelta` vs `timedelta` for Expiry:**
   Never use `timedelta(days=months * 30)` for legal or safety certifications (e.g. First Aid, Rigging, Scaffolding Inspector). Always use `dateutil.relativedelta.relativedelta(months=...)` to match true calendar expiry dates.
2. **Auto-Issue on Session Completion:**
   Ensure `action_done()` verifies that `not line.certification_id` before creating new records, preventing duplicate certificate generation if a session is re-evaluated.

---

## Verification

In Odoo Shell:
```python
courses = env['hse.training.course'].search([])
sessions = env['hse.training.session'].search([])
certs = env['hse.certification'].search([])
print(f"Courses: {len(courses)}, Sessions: {len(sessions)}, Certifications: {len(certs)}")
for cr in certs:
    print(cr.name, cr.employee_id.name, cr.course_id.name, cr.session_id.name, cr.expiry_date, cr.state)
```
Confirm all certificates carry valid reference numbers, linked sessions, and correct calendar expiry dates.
