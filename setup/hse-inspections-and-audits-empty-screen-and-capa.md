# HSE Inspections & Audits Empty Screen, Context Filter Pitfall, & CAPA Action Linkage

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `setup`, `hse`, `safety`, `inspection`, `audit`, `checklist`, `capa`, `demo-data`, `smart-button`, `context-filter`

---

## Problem

When navigating to **Safety > Compliance & Control > Inspections & Audits** (`action_hse_inspection`):
1. **Empty Screen:** The list view showed zero records in clean or production environments.
2. **Restrictive Default Filter (`my_inspections`):** The window action had `context="{'search_default_my_inspections': 1}"`. This filtered records strictly by `inspector_id == uid`, hiding audits and inspections performed by other safety engineers or external third-party auditors.
3. **Orphaned CAPA Actions on Inspection Form:** When a checklist item failed (`result == 'fail'`), transitioning to Done (`action_done()`) automatically generated corrective `hse.action` records. However, `hse.inspection` lacked computed fields (`action_ids`, `action_count`) and had an empty `oe_button_box`, making it impossible for auditors to view or navigate to the generated actions from the inspection form.
4. **Premature Completion Loophole:** Inspections could be transitioned directly from Draft to Done without evaluating any checklist item.
5. **Missing Mixin Fields:** `wbs_id` and `location` from `hse.project.mixin` were missing from both the list and form views.

---

## Root Cause

1. Initial demo data did not seed actual `hse.inspection` records, only template definitions.
2. The default window action context assumed single-user ownership, which contradicts multi-inspector construction sites.
3. Bidirectional linkage fields (`action_ids`, `action_count`) were omitted on `hse.inspection`.

---

## Solution ✅

### 1. Model Enhancements in `hse_inspection.py`

Add CAPA linkage, item counters, smart button, and workflow guardrails:

```python
class HseInspection(models.Model):
    _name = 'hse.inspection'
    _description = 'HSE Inspection & Audit'
    _inherit = ['hse.project.mixin', 'mail.thread', 'mail.activity.mixin']

    action_ids = fields.Many2many(
        'hse.action',
        string='CAPA Actions',
        compute='_compute_action_ids',
        help="All corrective actions spawned from failed checklist items."
    )
    action_count = fields.Integer(
        string='Action Count',
        compute='_compute_action_ids',
        help="Number of corrective actions linked to this inspection."
    )
    passed_count = fields.Integer(string='Passed Items', compute='_compute_item_counts')
    failed_count = fields.Integer(string='Failed Items', compute='_compute_item_counts')

    @api.depends('line_ids.action_id')
    def _compute_action_ids(self) -> None:
        for rec in self:
            actions = rec.line_ids.mapped('action_id')
            rec.action_ids = actions
            rec.action_count = len(actions)

    @api.depends('line_ids.result')
    def _compute_item_counts(self) -> None:
        for rec in self:
            rec.passed_count = len(rec.line_ids.filtered(lambda l: l.result == 'pass'))
            rec.failed_count = len(rec.line_ids.filtered(lambda l: l.result == 'fail'))

    def action_start(self) -> None:
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Please select a checklist template or add checklist items before starting."))
            rec.state = 'in_progress'

    def action_done(self) -> None:
        for rec in self:
            evaluated = rec.line_ids.filtered(lambda l: l.result in ('pass', 'fail'))
            if not evaluated:
                raise ValidationError(_("You cannot complete an inspection without evaluating at least one checklist item."))
            rec.state = 'done'
            rec._auto_create_actions()

    def action_reset_draft(self) -> None:
        for rec in self:
            if rec.state == 'done' and not self.env.user.has_group('construction_hse.group_hse_manager'):
                raise UserError(_("Only HSE Managers can reset a completed inspection or audit to draft."))
            rec.state = 'draft'

    def action_view_actions(self) -> dict:
        self.ensure_one()
        actions = self.action_ids
        action_data = {
            'name': _('CAPA Actions'),
            'type': 'ir.actions.act_window',
            'res_model': 'hse.action',
            'domain': [('id', 'in', actions.ids)],
        }
        if len(actions) == 1:
            action_data.update({'view_mode': 'form', 'res_id': actions.id})
        else:
            action_data.update({'view_mode': 'list,form'})
        return action_data
```

### 2. View Enhancements in `hse_inspection_views.xml`

1. Populate `oe_button_box` with CAPA Actions smart button.
2. Add `wbs_id`, `location`, and `subcontractor_id` to tree and form views.
3. Remove restrictive `search_default_my_inspections` from window action context (`context="{}"`).

---

## ⚠️ Pitfalls

1. **Window Action Context Filters:**
   Avoid applying `'search_default_my_...': 1` on compliance or audit menus where managers need full site visibility across all inspectors and subcontractors.
2. **Auto-Created Action Duplication:**
   Ensure `_auto_create_actions()` filters by `l.result == 'fail' and not l.action_id` to prevent creating duplicate actions if `action_done()` is re-invoked.

---

## Verification

In Odoo Shell:
```python
inspections = env['hse.inspection'].search([])
for ins in inspections:
    print(ins.name, ins.kind, ins.project_id.name, ins.score, ins.state, ins.action_count)
```
Ensure all inspections and audits load with accurate compliance scores, failed item findings, and linked CAPA actions.
