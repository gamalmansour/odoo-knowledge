# Dynamic Portal Section Visibility via Security Groups

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                   |
| Last Verified | 2026-06-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `portal`, `security`, `groups`, `dynamic-visibility`, `res.users`

---

## Problem

> In custom portal portals, UI sections (like "Shelf Stock", "Photos") are often hardcoded to show/hide based on a user's role (e.g., `t-if="is_merch"`). This becomes inflexible when admins need to grant specific sections to users who don't strictly fit into the hardcoded role definitions, or when roles evolve. 
> 
> Also, using Odoo's `implied_ids` in `res.groups` XML definitions makes it impossible for an administrator to un-tick a sub-group if the parent group is active.

## Root Cause

> Hardcoding visibility to `representative_type` bypasses Odoo's standard security architecture. While `implied_ids` natively handle role inheritance, they strictly enforce that a child group *cannot* be removed while the parent is assigned, restricting granular control.

## Solution ✅

> 1. Define independent security groups for each portal section in `security/*.xml`. Do **NOT** use `implied_ids` to automatically link these sections to a base role.
> 2. Implement python logic in `res_users.py` by overriding the role field's behavior (e.g., `_sync_representative_type_groups`). When a user's role changes, programmatically use `Command.link()` to add the default section groups for that role.
> 3. Add `fields.Boolean` toggles for each section directly on the `res.users` model using `compute` and `inverse` to read/write from `group_ids`. This makes it simple to manage from the backend user form.
> 4. In `controllers/portal.py`, write helper methods (`_can_see_shelf_stock`, etc.) that check if the user has the group via `user.has_group()`.
> 5. Pass these booleans to the portal template rendering context, and replace static `t-if="is_merch"` with dynamic `t-if="can_see_shelf_stock"`.

```python
# Example of dynamic linking without implied_ids
def _sync_representative_type_groups(self):
    # ... logic to assign base role group ...
    for user in self:
        default_groups = get_defaults_for_role(user.role)
        commands = []
        for sg in all_section_groups:
            if sg in default_groups and sg not in user.group_ids:
                commands.append(Command.link(sg.id))
            elif sg not in default_groups and sg in user.group_ids:
                commands.append(Command.unlink(sg.id))
        user.sudo().write({'group_ids': commands})
```

## ⚠️ Pitfalls

- **Group Caching:** `has_group()` uses the ORM cache. When modifying groups dynamically during portal operations (which shouldn't happen often, usually it's backend admins), the portal user might need to log out and log back in or the cache needs to clear. But usually, admins change it, so it's fine.
- **`implied_ids` vs `Command.link`:** Never mix `implied_ids` with manual toggle buttons in `res_users_views.xml`. If a group is implied, the backend UI checkbox will refuse to un-tick.
- **Access Error on `res.groups`:** Always use `.sudo()` or `Command.link` properly when modifying user groups from the backend if the modifying user has limited access.

## Verification

> Check the User form in the backend. Change their role. Observe the section toggles automatically turning ON/OFF based on the defaults. Then manually turn OFF one section and save. It should stay OFF. Check the portal view to verify that the section is hidden.

```bash
# None
```

## References

- Related to `sale_visit` module backend UI.
