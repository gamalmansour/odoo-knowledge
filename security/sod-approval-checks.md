# Segregation of Duties (SoD) in Custom Approval Engines

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-06-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `sod`, `approvals`, `workflow`

---

## Problem

> Custom dynamic approval workflows often lack Segregation of Duties (SoD) by default. This leads to two critical security flaws:
> 1. A user can approve a request they created themselves.
> 2. A single user can approve multiple stages of the same request, bypassing multi-level checks.

## Root Cause

> Standard groups/permissions only define WHO has the role to approve, but not contextual rules relating the user to the specific record or previous actions on that record.

## Solution ✅

> Add explicit context-aware Python checks within the `action_approve_current` (and reject) methods of your approval mixin.

```python
def action_approve_current(self):
    for rec in self:
        # Check standard role-based permissions first
        stage = rec.current_approval_stage_id
        if not self.env.user.groups_id & stage.group_ids and not self.env.is_superuser():
            raise UserError(_('You do not have the required permissions to approve this stage.'))

        # SoD Check 1: Requester cannot approve their own document.
        if 'create_uid' in rec and rec.create_uid.id == self.env.user.id and not self.env.is_superuser():
            raise UserError(_('Segregation of Duties: You cannot approve a document you created.'))

        # SoD Check 2: A user cannot approve multiple stages of the same document.
        previous_approvals = self.env['approval.request.line'].sudo().search_count([
            ('res_model', '=', self._name),
            ('res_id', '=', rec.id),
            ('state', '=', 'approved'),
            ('approver_id', '=', self.env.user.id),
        ])
        if previous_approvals > 0 and not self.env.is_superuser():
            raise UserError(_('Segregation of Duties: You have already approved a previous stage of this document.'))

        # Proceed with approval...
```

## ⚠️ Pitfalls

- Ensure you apply the same `create_uid` check to rejection methods, as requesters should cancel (not reject) their own documents.
- The SoD rules might clash with superusers or system administrators testing workflows. Provide a `not self.env.is_superuser()` bypass for admins.

## Verification

> 1. Create a document as User A. Try to approve as User A -> Should raise UserError.
> 2. Create as User A, approve Stage 1 as User B, try to approve Stage 2 as User B -> Should raise UserError.
