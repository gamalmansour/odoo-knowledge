# OpenEduCat Admission Register Not-Null Constraint on Headless/Public Submissions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `openeducat`, `op.admission`, `register_id`, `not-null`, `public-registration`

---

## Problem

When submitting candidate registrations or creating `op.admission` records headlessly, via public web forms, or in automated test fixtures without an explicitly selected `register_id`, PostgreSQL aborts the transaction with a `NotNullViolation`:

```text
ERROR: null value in column "register_id" of relation "op_admission" violates not-null constraint
DETAIL: Failing row contains (..., null value in column "register_id" ...)
psycopg2.errors.NotNullViolation: null value in column "register_id" of relation "op_admission" violates not-null constraint
```

## Root Cause

In standard OpenEduCat (`openeducat_admission`), `register_id = fields.Many2one('op.admission.register', 'Admission Register', required=True)` maps to a PostgreSQL `NOT NULL` constraint on column `register_id`. In collegiate or academic institutes, admissions are always grouped under structured semester admission registers. However, in corporate or industrial training centers (e.g. safety centers, Aramco contractor training), registrations happen continuously per course batch without students choosing an academic register.

## Solution ✅

Implement an auto-resolution and self-provisioning fallback inside an extension of `op.admission` using `default_get` and `create`:

```python
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api

class OpAdmission(models.Model):
    _inherit = 'op.admission'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'register_id' in fields_list and not res.get('register_id'):
            register = self.env['op.admission.register'].search([
                ('state', 'in', ['application', 'admission'])
            ], limit=1)
            if not register:
                register = self.env['op.admission.register'].search([], limit=1)
            if register:
                res['register_id'] = register.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('register_id'):
                course_id = vals.get('course_id')
                register = False
                if course_id:
                    register = self.env['op.admission.register'].search([
                        ('course_id', '=', course_id),
                        ('state', 'in', ['application', 'admission'])
                    ], limit=1)
                if not register:
                    register = self.env['op.admission.register'].search([
                        ('state', 'in', ['application', 'admission'])
                    ], limit=1)
                if not register:
                    register = self.env['op.admission.register'].search([], limit=1)
                if register:
                    vals['register_id'] = register.id
                else:
                    # Auto-provision an active register with term & academic year
                    year = self.env['op.academic.year'].search([], limit=1)
                    if not year:
                        year = self.env['op.academic.year'].create({
                            'name': 'Academic Year %s' % fields.Date.today().year,
                            'code': 'AY%s' % fields.Date.today().year,
                            'start_date': fields.Date.today(),
                            'end_date': fields.Date.today() + relativedelta(years=1),
                        })
                    term = self.env['op.academic.term'].search([], limit=1)
                    if not term:
                        term = self.env['op.academic.term'].create({
                            'name': 'Term 1',
                            'code': 'T1',
                            'academic_year_id': year.id,
                        })
                    default_course = course_id or self.env['op.course'].search([], limit=1).id
                    new_reg = self.env['op.admission.register'].create({
                        'name': 'General Training Admissions',
                        'course_id': default_course,
                        'start_date': fields.Date.today(),
                        'end_date': fields.Date.today() + relativedelta(years=1),
                        'academic_years_id': year.id,
                        'academic_term_id': term.id,
                        'state': 'admission',
                    })
                    vals['register_id'] = new_reg.id
        return super().create(vals_list)
```

## ⚠️ Pitfalls

1. **Course Dependency:** `op.admission.register` itself requires a `course_id`. When creating an auto-provisioned register, ensure a course is browsed or provided.
2. **State Gate:** Standard OpenEduCat blocks admission submission if `register.state not in ('application', 'admission')`. The fallback register must be initialized in state `'admission'`.

## Verification

Create an `op.admission` record without `register_id` in Python shell and confirm `record.register_id` is automatically populated and record saves cleanly without PostgreSQL error.
