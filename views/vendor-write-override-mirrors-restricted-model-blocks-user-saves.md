# Vendor `write()` Override That Mirrors Onto an Admin-Only Model Blocks Every User Save

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `AccessError`, `res.users`, `ir.ui.menu`, `third-party`, `write-override`, `mirror`, `no-op`, `scs_hide_menu_user_wise`

---

## Problem

> Users cannot save their own preferences — signature, language, notification
> settings. The error names a model they never touched:

```
AccessError: You are not allowed to modify 'Menu' (ir.ui.menu) records.
This operation is allowed for the following groups:
	- Role / Administrator
```

Only *some* users are affected, which makes it look random. On the live data:
a user with 31 hidden menus fails, a user with none succeeds. **23 users
affected.**

## Root Cause

`scs_hide_menu_user_wise` (SerpentCS) overrides `res.users.write` and, after
**every** write to **any** user, re-mirrors that user's hidden menus onto the
menu side:

```python
def write(self, vals):
    res = super().write(vals)
    for user in self:
        user.hide_menu_ids.write({"restrict_user_ids": [Command.link(user.id)]})
        ...
```

`ir.ui.menu` is writable only by `base.group_system`, and the mirror runs with
the **calling user's** rights. So a non-admin with at least one hidden menu
hits an AccessError on a bookkeeping write they neither asked for nor can
influence — `hide_menu_ids` is settable only by an administrator.

The mirror is also **pointless in that moment**: the link it writes is already
there. It does real work only when an administrator actually changes
`hide_menu_ids`.

## Solution ✅

> Do **not** reach for `sudo()`. Prune the commands that would change nothing,
> and skip the write entirely when none are left. Zero privilege escalation.

```python
class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def write(self, vals):
        if list(vals) == ['restrict_user_ids'] and self:
            commands = self._prune_noop_restrictions(vals['restrict_user_ids'])
            if isinstance(commands, list) and not commands:
                return True          # nothing would change -> no access check
            vals = dict(vals, restrict_user_ids=commands)
        return super().write(vals)
```

`_prune_noop_restrictions` drops `Command.LINK` for a user already linked and
`Command.UNLINK` for one not linked, and passes **every other command through
untouched** so a real edit is never silently swallowed.

Why this beats the obvious alternatives:

| Approach | Why not |
|---|---|
| `super(..., self.sudo()).write(vals)` on `res.users` | Escalates the **whole** user write — a user could then write any field on themselves |
| sudo only the mirror on `ir.ui.menu` | A user could call `ir.ui.menu.write({'restrict_user_ids': [(3, uid)]})` by RPC and **unhide** menus an admin hid |
| Edit the vendor module | Never modify third-party code; the next update erases it |
| Catch the AccessError | Swallows real failures too |

Pruning keeps the permission check **exactly where it was** for anything that
actually changes state.

## ⚠️ Pitfalls

- **A no-op write is still a write.** `Command.link` on an already-linked
  record does not short-circuit in Odoo — the ACL check runs regardless.
- **Test with `with_user()`, never as admin.** `TransactionCase` runs as
  superuser and this bug is invisible there (KB:
  `backend/env-su-guard-silently-passes-in-transactioncase.md`).
- **Confirm the fix did not grant anything.** After the fix the same user must
  still fail `env['ir.ui.menu'].with_user(u).check_access('write')`. If that
  starts passing, the fix escalated instead of pruning.
- The vendor's *unlink* branch is harmless in the common case:
  `previous_menus - user.hide_menu_ids` is empty, and `.write()` on an empty
  recordset never checks access. Only the link branch raises — which is why
  the symptom looks like "some users, some of the time".

## Verification

```python
u = env['res.users'].search([('login', '=', 'restricted@example.com')])
assert u.hide_menu_ids                                   # is actually restricted
u.with_user(u).write({'signature': '<p>x</p>'})          # must NOT raise

# and the fix must not have handed out rights:
try:
    env['ir.ui.menu'].with_user(u).check_access('write')
    raise AssertionError("the user should still NOT be able to write menus")
except AccessError:
    pass
```

Measured before and after on the live data: a user with 31 hidden menus went
from `AccessError` to a clean save, while still being denied write access on
`ir.ui.menu`.

## Related

- `backend/env-su-guard-silently-passes-in-transactioncase.md` — why this must be tested with `with_user`
- `views/menu-visibility-ormcache-keyed-by-groups.md` — the other defect in the same vendor module
