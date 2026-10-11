# `%(module.xmlid)d` does not substitute inside a Python field `domain=`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `domain`, `fields`, `xmlid`, `ref`, `ir.rule`, `groups_id`

---

## Problem

Copying the `ir.rule` / XML-data domain idiom into a **model field** definition
to restrict a Many2one to members of a security group:

```python
# models/activity_schedule.py — BROKEN
coach_id = fields.Many2one(
    'res.users',
    domain="[('groups_id', '=', %(activity_base.group_activity_coach)d)]")
```

The `%(...)d` is never resolved. The literal `%`-string reaches the web client as
the domain, and the field either raises an "invalid domain" / bad-format error or
silently filters nothing — depending on where it's first evaluated.

## Root Cause

`%(module.xml_id)d` substitution is a feature of **XML data files** and **`ir.rule`
`domain_force`** (Odoo resolves the xmlid to its DB id at load time). A field's
`domain=` string is **not** run through that resolver — it's shipped verbatim to
the client and evaluated there in a context that has no access to xmlids. Same
reason `ref('module.xmlid')` doesn't work in a field or view `domain=` attribute.

## Solution ✅

Pick one:

1. **Drop the hard domain** when the choice is admin-only configuration — let the
   admin pick the right record (simplest, what we shipped):

   ```python
   coach_id = fields.Many2one('res.users', string='Coach',
                              help='Assigned by an admin.')
   ```

2. **Filter by a stable, queryable attribute** instead of the xmlid — e.g. a group's
   `category_id` reached through a non-xmlid path, or another domainable field.

3. **Compute the allowed ids and inject a dynamic domain** via an `@api.onchange`
   or a computed `Many2many` of candidates, then `domain="[('id','in',candidate_ids)]"`.

4. If you truly need the group id in a **view**, resolve it server-side and pass it
   through the action `context`, then reference `context.get('coach_group_id')` — the
   view domain can read context keys, not xmlids.

## ⚠️ Pitfalls

- The bug is easy to miss in single-record admin testing if the domain "fails open"
  (filters nothing) rather than erroring — you only notice the missing restriction.
- The exact same limitation applies to `ref(...)` and `%(...)s`/`%(...)d` inside a
  **view** `domain="..."` attribute, not just field definitions.
- `ir.rule.domain_force` **does** support `%(xmlid)d` — don't over-correct and strip
  it there.

## Verification

Module installs clean and the field behaves; grep for the anti-pattern:

```bash
grep -rnE "domain\s*=\s*[\"'].*%\(" --include="*.py" <module>/models/
```

## References

- Related file: `security/multi-company-record-rules.md` (where `%(...)d` in
  `domain_force` is correct and expected)
- Code: `activity/activity_catalog/models/activity_schedule.py` (`coach_id`)
