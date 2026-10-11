# "Access Rights Inconsistency" View Warning: the Fix Must Load BEFORE the Validated Module

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19 (validator introduced ~17+)             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `validation`, `access-rights`, `groups`, `portal`, `load-order`, `odoo-sh`, `field-groups`

---

## Problem

> Deploying to Odoo.sh shows `WARNING ... Access Rights Inconsistency ... element depends
> on the field "employee_overtime" that is not accessible ... shown in the view for
> groups: 'base.group_user' | 'base.group_portal'` — pointing at YOUR view file, although
> your view never touches that field.

## Root Cause

Two mechanisms interact:

1. **Granting a portal ACL on a backend model widens the view validator's audience.**
   When a module gives `base.group_portal` read access on e.g. `hr.leave.allocation`,
   the validator counts portal among the potential viewers of every backend view on
   that model. Any element bound to an internal-only field (like
   `hr_holidays_attendance.employee_overtime`, `groups='base.group_user'`) becomes
   "inconsistent" — and the warning fires while validating *whichever custom view gets
   (re)written during the upgrade*, i.e. yours.

2. **During `-u module`, the registry only contains python of modules already loaded in
   the dependency graph.** A fix placed in a module that loads AFTER the validated one
   (view inherit patch OR python field-groups override) is invisible at validation time
   — everything looks fine at runtime and on clean-DB installs, but the warning returns
   on every upgrade/deploy. Clean-DB test runs can't catch this: at install time the
   portal ACL doesn't exist yet when the earlier module validates.

## Solution ✅

Put the field-groups extension in (or before) the module whose views get validated —
its own python is always loaded before its data:

```python
# In the module that owns the flagged view (NOT in the portal module):
class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'
    employee_overtime = fields.Float(groups='base.group_user,base.group_portal')
```

Verification method: upgrade the module **twice** against a DB where the portal ACL
already exists and grep the log — a fix that only silences the first run is transitional,
not real:

```bash
odoo-bin -d db -u my_module --stop-after-init --log-level=warn 2>&1 | grep -c "Access Rights"
```

## ⚠️ Pitfalls

- A view-inherit patch (`position="attributes"` adding `groups=` on the element) suffers
  the SAME load-order blindness if it lives in a later module — prefer the field-level
  override.
- Widening `groups` on the field is safe only when record rules already scope the portal
  user to their own records — check that first.
- Related fields: the validator uses the field's own `groups`; runtime shell checks
  (`model._fields[name].groups`) can look correct while upgrade-time validation still
  fails — that's the load-order gap, not a caching issue.
- Companion warning `Two fields (...) have the same label` — just give your custom field
  a distinct `string=`.

## Versions

Verified on Odoo 19.0 (local + Odoo.sh log).
