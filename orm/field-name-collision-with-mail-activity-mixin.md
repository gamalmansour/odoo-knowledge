# Naming a field `activity_ids` (or `activity_state`/`activity_type_id`) shadows `mail.activity.mixin` and breaks its related fields

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `fields`, `mail`, `mail.activity.mixin`, `collision`, `related`, `install-blocker`

---

## Problem

Adding an innocent-looking `activity_ids` M2M to a model that (directly or via a
core inherit) mixes in `mail.activity.mixin` makes the **whole registry fail to
build**:

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    activity_ids = fields.Many2many('activity.activity', ...)   # BOOM
```

```
KeyError: Field activity_type_id referenced in related field definition
product.template.activity_type_id does not exist.
```

The error names `activity_type_id`, which you never touched — so it's easy to
chase the wrong field.

## Root Cause

`mail.activity.mixin` defines `activity_ids` as a `One2many` to `mail.activity`,
plus several fields **related through it**: `activity_state`, `activity_type_id`,
`activity_user_id`, `activity_date_deadline`, `activity_summary`, etc. Many core
models inherit this mixin (`product.template`, `sale.order`, `res.partner`,
`crm.lead`, `project.task`, …).

Redefining `activity_ids` with a different comodel **overrides** the mixin's
field. The mixin's `activity_type_id = fields.Selection(related='activity_ids.activity_type_id')`
(and friends) then point through your M2M, whose target model has no such field —
so `setup_related` raises at load time and the module won't install.

## Solution ✅

Never reuse the `activity_*` field namespace of the mail mixin. Prefix your field
so it can't collide:

```python
kit_activity_ids = fields.Many2many(
    'activity.activity', 'activity_kit_product_rel', 'product_tmpl_id', 'activity_id',
    string='Activities')
```

Reserved-by-the-mixin names to avoid on any mail-activity model:
`activity_ids`, `activity_state`, `activity_type_id`, `activity_type_icon`,
`activity_user_id`, `activity_date_deadline`, `activity_summary`,
`activity_exception_decoration`, `activity_exception_icon`, `activity_calendar_event_id`.

## ⚠️ Pitfalls

- The traceback blames the mixin's *related* field, not your field — grep your
  diff for the actual name you added (`activity_ids`) instead.
- Same trap for `message_ids`/`message_follower_ids` (from `mail.thread`) and
  `website_*` fields on website-published models. When extending a core model,
  check what mixins it already carries before picking a field name.
- A quick guard: `self.env['product.template']._fields.get('activity_ids')` in a
  shell shows the mixin already owns it.

## Verification

```bash
odoo-bin -c conf -d db -i <module> --stop-after-init   # must reach "Registry loaded"
```

## References

- Code: `activity/activity_store/models/product_template.py` (`kit_activity_ids`)
- Related file: `orm/related-field-keyerror-reference.md`
