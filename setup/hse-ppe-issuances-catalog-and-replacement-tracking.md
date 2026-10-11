# HSE PPE Issuances Catalog, Lifespan Replacement, and Activity Tracking

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `ppe`, `issuance`, `catalog`, `lifespan`, `replacement`, `mail.activity.mixin`, `smart-button`

---

## Problem

When accessing the **Safety > PPE > Issuances** menu in a clean or freshly restored Odoo database, the screen is completely blank with zero records. Furthermore:
1. `hse.ppe.type` (the PPE catalog) had no navigation menu in the UI, making it impossible for safety officers to configure standard equipment without developer mode.
2. `hse.ppe.issuance` only inherited `mail.thread` without `mail.activity.mixin`, preventing safety officers from scheduling follow-up activities or equipment return/inspection reminders.
3. Equipment replacement dates had to be manually guessed and typed on each line because `hse.ppe.type` lacked a `default_lifespan_days` parameter.
4. An issuance voucher could be confirmed (`action_done`) with zero equipment lines or non-positive quantities.

## Root Cause

1. **Missing Initial Master & Transactional Seed Data:**
   In demo and fresh databases, no `hse.ppe.type` or `hse.ppe.issuance` records are installed by default unless explicitly seeded.
2. **Missing Catalog Menu Action:**
   `action_hse_ppe_type` was defined in XML views but omitted from `menus.xml`, leaving PPE types inaccessible in standard navigation.
3. **Incomplete Mail Mixin Inheritance:**
   Inheriting only `mail.thread` without `mail.activity.mixin` limits Chatter to message logs, disabling activity scheduling.
4. **Lack of Lifecycle Duration & Validation Guardrails:**
   Without lifespan metadata on PPE items, safety managers cannot forecast when helmets (e.g. 730 days) or harnesses (365 days) must be replaced. Also, `action_done` had no defensive checks on line count or positive quantity.

## Solution ✅

### 1. Upgrade `hse.ppe.type` and `hse.ppe.issuance` in Python
Add item codes, lifespan days, issuance aggregation, `mail.activity.mixin`, and validation:

```python
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HsePpeType(models.Model):
    _name = 'hse.ppe.type'
    _description = 'PPE Type'
    _order = 'category, name'

    name = fields.Char(string='PPE Name', required=True)
    code = fields.Char(string='Item Code')
    category = fields.Selection([
        ('head', 'Head Protection'),
        ('eye', 'Eye/Face Protection'),
        ('hearing', 'Hearing Protection'),
        ('respiratory', 'Respiratory Protection'),
        ('hand', 'Hand Protection'),
        ('foot', 'Foot Protection'),
        ('body', 'Body Protection'),
        ('fall', 'Fall Protection'),
        ('other', 'Other')
    ], string='Category', required=True, default='head')
    default_lifespan_days = fields.Integer(string='Lifespan (Days)', default=180)
    active = fields.Boolean(default=True)
    issuance_line_ids = fields.One2many('hse.ppe.issuance.line', 'ppe_type_id', string='Issuances')
    issuance_count = fields.Integer(string='Issued Count', compute='_compute_issuance_count')

    def _compute_issuance_count(self) -> None:
        read_group_res = self.env['hse.ppe.issuance.line'].read_group(
            [('ppe_type_id', 'in', self.ids)],
            ['ppe_type_id'],
            ['ppe_type_id']
        )
        mapped = {r['ppe_type_id'][0]: r['ppe_type_id_count'] for r in read_group_res}
        for rec in self:
            rec.issuance_count = mapped.get(rec.id, 0)


class HsePpeIssuance(models.Model):
    _name = 'hse.ppe.issuance'
    _description = 'PPE Issuance'
    _inherit = ['hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    def action_done(self) -> None:
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Cannot issue PPE voucher without any equipment lines."))
        for line in self.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Quantity for '%s' must be strictly positive.") % line.ppe_type_id.name)
        self.write({'state': 'done'})
```

### 2. Auto-compute Replacement Due Date on Line Selection
```python
class HsePpeIssuanceLine(models.Model):
    _name = 'hse.ppe.issuance.line'
    _description = 'PPE Issuance Line'

    @api.onchange('ppe_type_id')
    def _onchange_ppe_type_id(self) -> None:
        if self.ppe_type_id and self.ppe_type_id.default_lifespan_days:
            base_date = self.issuance_id.issue_date or fields.Date.context_today(self)
            self.replacement_due = base_date + relativedelta(days=self.ppe_type_id.default_lifespan_days)
```

### 3. Expose PPE Catalog Menu in `menus.xml`
```xml
<menuitem id="menu_hse_ppe_types"
          name="PPE Types"
          parent="menu_hse_ppe"
          action="action_hse_ppe_type"
          sequence="20"/>
```

### 4. Seed Standard Catalog & Issuance Vouchers
Seed items across head, foot, body, eye, fall, and respiratory categories with project assignments.

## ⚠️ Pitfalls

- **Relational Field Traversals in Domains:**
  When filtering overdue or upcoming replacements, do not create complex non-stored cross-model computed fields in search domains. Keep `replacement_due` stored on `hse.ppe.issuance.line`.
- **Chatter Activity Mixin Missing:**
  Chatter tags (`<chatter/>`) in Odoo 18 expect models to inherit `mail.activity.mixin` if activity schedules are used. Omitting it causes silent failures or missing activity buttons.
- **Stock Move Decoupling:**
  By default in construction operations, safety gear is issued on site without strictly blocking on warehouse standard picking moves unless `ppe_use_stock` is enabled in configuration. Always verify before enforcing physical stock quants.

## Verification

```bash
# Check record counts in shell
python -c "
import odoo
from odoo import api, SUPERUSER_ID
with odoo.registry('hadhoud_demo').cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('PPE Types:', env['hse.ppe.type'].search_count([]))
    print('PPE Issuances:', env['hse.ppe.issuance'].search_count([]))
"
```

## References

- Related models: `construction_hse/models/hse_ppe.py`
- Related views: `construction_hse/views/hse_ppe_views.xml`
- Related menus: `construction_hse/views/menus.xml`
