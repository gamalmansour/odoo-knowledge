# Restricting Who Can Move a Record Into a Kanban Pipeline Stage (Per-Stage Transition ACL)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `stage`, `kanban`, `workflow`, `access-rights`, `write-override`, `lockout`

---

## Problem

A business wants stage-level authorisation on a kanban pipeline: *"only the Bid Manager may drag a tender into **Submitted**"*. Odoo's standard access layer cannot express this — `ir.model.access` and `ir.rule` gate **the record**, not **the value being written into a field**. A user who may edit the record may set `stage_id` to any stage.

Naive implementations fail in one of three ways:

- Gating the **button** only (`action_mark_won`) — the user just drags the kanban card instead, or edits the field in the list view.
- Gating with a `@api.constrains('stage_id')` — fires *after* the row is written, and constrains cannot see who moved it vs. who merely touched another field.
- Hard-coding a group in Python — the customer then wants a different person per stage, and every change needs a developer.

## Root Cause

Stage transition is a **value-level** permission, and Odoo has no declarative layer for it. It must be enforced imperatively, and the only place that catches *every* entry path (kanban drag-and-drop, list inline edit, form edit, workflow buttons, `write()` from other modules) is an override of `write()` on the record model.

## Solution ✅

**1. Two optional config fields on the stage model** — users OR groups, so the rule can be role-based instead of person-based:

```python
class TenderStage(models.Model):
    _name = 'tender.stage'

    allowed_user_ids = fields.Many2many(
        'res.users',
        'tender_stage_allowed_user_rel', 'stage_id', 'user_id',
        string='Allowed Users',
        help="Users allowed to move a record INTO this stage. "
             "Leave empty (with Allowed Groups) to allow everyone.",
    )
    allowed_group_ids = fields.Many2many(
        'res.groups',
        'tender_stage_allowed_group_rel', 'stage_id', 'group_id',
        string='Allowed Groups',
        help="Groups allowed to move a record INTO this stage. OR-ed with Allowed Users.",
    )

    def _is_transition_allowed(self, user=None) -> bool:
        self.ensure_one()
        user = user or self.env.user
        if not self.allowed_user_ids and not self.allowed_group_ids:
            return True                                   # empty = open (fail-open by design)
        if user.has_group('construction_tender.group_tender_admin'):
            return True                                   # admin never gets locked out
        if user in self.allowed_user_ids:
            return True
        return bool(user.groups_id & self.allowed_group_ids)

    def _check_transition_allowed(self) -> None:
        if self.env.su or self.env.context.get('tender_skip_stage_guard'):
            return                                        # crons / module data / opt-out
        for stage in self:
            if stage._is_transition_allowed():
                continue
            raise UserError(_(
                'You are not allowed to move records into the stage "%(stage)s".\n\n'
                'Allowed users: %(users)s\n'
                'Allowed groups: %(groups)s',
                stage=stage.display_name,
                users=', '.join(stage.allowed_user_ids.mapped('name')) or _('none'),
                groups=', '.join(stage.allowed_group_ids.mapped('display_name')) or _('none'),
            ))
```

**2. Enforce in `write()` on the record model — the single funnel:**

```python
class TenderOpportunity(models.Model):
    _name = 'tender.opportunity'

    @api.model_create_multi
    def create(self, vals_list: list) -> models.Model:
        records = super().create(vals_list)
        records.mapped('stage_id')._check_transition_allowed()
        return records

    def write(self, vals: dict) -> bool:
        if vals.get('stage_id'):
            self.env['tender.stage'].browse(vals['stage_id'])._check_transition_allowed()
        return super().write(vals)
```

**3. Expose the fields** with `widget="many2many_tags"` on the stage tree/form. Keep write access on the stage model restricted to managers, so ordinary users can *see* who is authorised but not edit the rule.

## ⚠️ Pitfalls

- **Fail-open, not fail-closed.** Empty must mean "everyone". A fail-closed default freezes the whole pipeline the moment the module is installed, before anyone has configured a thing.
- **Always give one group an unconditional bypass** (the module's admin group). Six months later the single named approver leaves the company, gets archived, and nobody can move a record — with no way to fix it except SQL. Note that an archived user silently disappears from the m2m (`active_test`), so the stage becomes *stricter*, not looser.
- **`self.env.su` / context escape hatch is mandatory.** Crons, `ir.cron` running as `base.user_root`, module data loading, and other modules' server-side transitions will otherwise crash in production. Expose `with_context(<module>_skip_stage_guard=True)` for legitimate programmatic moves.
- **Name the authorised users in the error message.** "Access denied" generates a support ticket; "Allowed users: Ahmed, Mona" generates a phone call to Ahmed.
- **Check the target stage once per `write()` call, not per record.** `vals['stage_id']` is a single value, so a mass move of 5,000 records costs one permission check. Putting the check in a per-record loop (or a `constrains`) turns a bulk stage move into thousands of `has_group` calls.
- **Don't gate the buttons instead of `write()`.** `action_mark_won()` calls `self.write({'stage_id': ...})`, so a `write()` guard covers the buttons for free — the reverse is not true.
- **Watch the m2m relation table name.** PostgreSQL truncates identifiers at 63 chars; name the relation table explicitly rather than letting Odoo autogenerate `model_a_model_b_rel`.
- **`vals.get('stage_id')` is deliberately falsy-checked** — clearing the stage (`False`) is not "moving into a restricted stage" and must not raise.

## Verification

```bash
# 1. Upgrade and confirm no install error
./odoo-bin -c odoo17_dev.conf -u construction_tender -d <db> --stop-after-init

# 2. As a Tender User with the stage restricted to someone else:
#    - drag the card in kanban        -> UserError naming the allowed users
#    - edit stage_id in the list view -> same UserError
#    - press "Mark Won" on a restricted Won stage -> same UserError
# 3. As a Tender Administrator: all three succeed (bypass).
# 4. Clear both fields on the stage: all users succeed again (fail-open).
# 5. Run the deadline-reminder cron: no crash (env.su bypass).
```

## References

- Implemented in `construction_tender` v17.0.1.3.0 — `models/tender_stage.py`, `models/tender_opportunity.py`, `views/tender_stage_views.xml`
- Related file: `security/sod-approval-checks.md` — the same fail-open + explicit-bypass reasoning applied to approval chains
- Related file: `orm/dynamic-phases-crm-spirit.md`
