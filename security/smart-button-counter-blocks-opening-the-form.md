# A Smart-Button Counter Blocks Opening the Form Entirely

| Field         | Value        |
|---------------|--------------|
| Category      | security     |
| Odoo Versions | All          |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `access-rights`, `smart-button`, `computed-fields`, `search_count`, `sudo`, `cross-module`

---

## Problem

Clicking any project in the list — as the **administrator** — produced a modal instead of the
record:

```
Access Error
You are not allowed to access 'Material Purchase Requisition'
(construction.material.requisition) records.

This operation is allowed for the following groups:
    - Construction Management/Requisition Manager
    - Construction Management/Requisition User
```

The main record of the main application could not be opened at all. Not a button that failed
when pressed — the **form refused to load**.

## Root Cause

The smart-button counters are computed just to render the form:

```python
def _compute_counts(self):
    for rec in self:
        rec.work_order_count = len(rec.work_order_ids)
        rec.material_req_count = self.env['construction.material.requisition'].search_count(
            [('project_id', '=', rec.id)])
```

`search_count` runs as the current user, so a user lacking rights on the *other* module raises
`AccessError` while the compute is still running — before a single field is painted. The count
exists only to put a number on a button the user may never press, and it takes down the whole
screen.

It bites the administrator too: `base.user_admin` is not automatically a member of every
custom group a suite defines, so "it works for admin" is not a safe assumption.

Nothing in an ORM test suite catches this. `TransactionCase` runs as SUPERUSER, which bypasses
ACLs entirely, and no test renders a view. Here 248 green tests and five end-to-end ORM
scenarios all passed while the form was unopenable.

## Solution ✅

Read cross-module counters with `sudo()`. A count is aggregate metadata; pressing the button
still runs the target action under the user's own rights, so nothing is disclosed that the
button would not already gate.

```python
def _compute_counts(self):
    """Smart-button counters.

    The cross-module counts are read with sudo on purpose. They are computed just to open
    the project form, so a user without rights on the OTHER module could not open a project
    at all — even the administrator hit "You are not allowed to access 'Material Purchase
    Requisition'" merely by clicking a project.
    """
    for rec in self:
        rec.work_order_count = len(rec.work_order_ids)
        rec.subcontract_count = len(rec.sudo().subcontract_ids)
        rec.material_req_count = self.env['construction.material.requisition'].sudo().search_count(
            [('project_id', '=', rec.id)])
```

Note that One2many fields have the same exposure: `len(rec.subcontract_ids)` reads
`contract.subcontractor` under the user's rights just as surely as an explicit search.

Sweep for the pattern across the codebase:

```bash
grep -rn "search_count(\[" --include="*.py" */models/ | grep -v "sudo()"
```

## ⚠️ Pitfalls

- Do **not** fix it by granting the group. That hands every project user rights on an
  unrelated module to satisfy a number on a button.
- `compute_sudo=True` on the field is not equivalent for a stored=False compute triggered by
  a form read; being explicit about which reads are elevated is clearer and keeps the
  user-scoped counts (same-module ones) honest.
- Check the other direction too: any `_compute_` that touches a different module's model,
  including `mapped()`, `filtered()` over a related One2many, or `read_group`.
- If a count must genuinely reflect only what the user may see, keep it user-scoped and wrap
  it so a failure yields 0 instead of an exception — never let it break the form.

## Verification

Open the form in a browser as a user **without** the other module's group. This class of
defect is invisible to the ORM test suite and to `odoo-bin shell` scripts, which is exactly
why it survived a full clean-database end-to-end pass.

## References

- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `security/noupdate-group-change-never-reaches-existing-databases.md`
- Related file: `views/monetary-column-totals-render-as-dashes.md`
