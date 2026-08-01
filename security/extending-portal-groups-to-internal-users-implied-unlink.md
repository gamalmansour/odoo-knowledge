# Extending Portal-Only Groups to Internal Users — the Implied `base.group_portal` Trap

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 19 (removal mechanics apply to all)        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-28                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `groups`, `implied_ids`, `base.group_portal`, `internal-users`, `user-type`, `Command.unlink`, `all_group_ids`

---

## Problem

A feature built for portal users (representative types, section access groups, supervisor hierarchy on `res.users`) must now also work for INTERNAL users (field team upgraded to internal). Relaxing the view `invisible="not share"` conditions and field domains is NOT enough — assigning any representative group to an internal user still dies with:

```
ValidationError: User '...' cannot be at the same time in exclusive groups 'Role / User', 'Role / Portal'.
```

## Root Cause

Three coupled layers assume "representative = portal":

1. **View conditions** — every panel carries `or not share`.
2. **Field domains** — `[('share', '=', True), ...]` on the supervisor/subordinate m2m.
3. **Group implication** — every representative/section group has `implied_ids = [Command.link(base.group_portal)]`, and in **Odoo 19 implication is resolved dynamically** (`all_group_ids`), so granting the group to an internal user transitively grants Portal → `_check_disjoint_groups` rejects the mix of exclusive role groups.

**The extra trap:** deleting the `implied_ids` line from the XML does NOTHING on upgrade — a removed `<field>` is simply not written, so the old link stays in the DB and the crash persists. Verified: after removing the lines and `-u`, the ValidationError still fired.

## Solution ✅

1. **Explicitly unlink** the implication in the groups XML (a removed line ≠ a removed link):

```xml
<field name="implied_ids" eval="[Command.unlink(ref('base.group_portal'))]"/>
```

2. Keep portal provisioning working by moving the portal-group link into the type-sync, gated on the user already being portal:

```python
if user.share and portal_group not in user.group_ids:
    commands.append(Command.link(portal_group.id))
```

Internal users keep their internal type and just carry the representative/section groups.

3. Drop `('share', '=', True)` from the m2m domains and the `not share` view conditions — visibility keys on `representative_type` instead.

## ⚠️ Pitfalls

- **Existing portal reps are safe** only because the sync had added `base.group_portal` to them EXPLICITLY; if portal membership existed *only* through the implication, removing it would (dynamically, in 19) strip their portal access — audit `group_ids` vs `all_group_ids` before shipping.
- **Group record rules now bind internal users too**: an internal user holding the rep group inherits its permissive group rules, which in Odoo's semantics can NARROW a previously unrestricted internal user (group rules OR among themselves, AND with global). Here that was the requested behavior ("same conditions"), but audit rules attached to the shared groups.
- Verify on a DB copy — the failure only appears when a live internal user receives the group (`_check_disjoint_groups` is a write-time constraint, invisible to `-u`).

## Verification

On a copy of the production-test DB (Odoo 19): upgrade passes; existing portal rep keeps `share=True` + portal group; a new internal user with `representative_type='sales'` stays internal with the sales + section groups; an internal supervisor supervises a mixed internal+portal team and the portal team-targets traversal picks up both. Regression tests: `sale_visit/tests/test_internal_representative.py`.

## References

- Fixed files: [security/representative_groups.xml](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/security/representative_groups.xml), [models/res_users.py](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/models/res_users.py), [views/res_users_views.xml](file:///Users/gamal/odoo/odoo19.0/custom/sale_visit/views/res_users_views.xml)
- Related KB: [odoo-19-res-users-groups-id-renamed-group-ids](../orm/odoo-19-res-users-groups-id-renamed-group-ids.md), [per-stage-transition-acl-on-kanban-pipelines](per-stage-transition-acl-on-kanban-pipelines.md)
