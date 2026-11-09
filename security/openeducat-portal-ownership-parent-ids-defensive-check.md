# OpenEduCat Portal Authorization: AttributeError on student.parent_ids vs parent_id

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-09                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `openeducat`, `portal`, `security`, `authorization`, `op.student`, `parent_ids`, `parent_id`, `AttributeError`

---

## Problem

When an external portal user accesses customer portal routes for candidate documents or certificates (e.g. `/my/certificate/<id>` or `/my/certificate/download/<id>`), attempting to access records belonging to another candidate triggers an unhandled `AttributeError` instead of raising HTTP 403 `Forbidden`:

```
AttributeError: 'op.student' object has no attribute 'parent_ids'. Did you mean: 'parent_id'?
```

This crashes the portal worker process with an HTTP 500 Internal Server Error in production logs, leaking stack trace information and failing to cleanly deny unauthorized access.

## Root Cause

In OpenEduCat Community 17.0, `op.student` defines `parent_id` (Many2one to `res.partner`), and does NOT define a Many2many `parent_ids` field.
Some enterprise extensions or custom modules introduce `parent_ids` (or an `op.parent` model). When portal ownership verification assumes `student.parent_ids` exists without inspection, evaluating:

```python
if student.partner_id.id != user.partner_id.id:
    parent_partner_ids = student.parent_ids.mapped('user_id.partner_id.id')
    if user.partner_id.id not in parent_partner_ids:
        raise Forbidden(_("You do not have permission to view this certification."))
```

crashes with `AttributeError` whenever `student.partner_id.id != user.partner_id.id`.

## Solution ✅

Use defensive attribute checking with `hasattr()` to dynamically support both Community (`parent_id`) and Enterprise / Multi-parent schemas (`parent_ids`):

```python
from werkzeug.exceptions import Forbidden
from odoo import _

# In customer portal controller:
if not is_internal:
    # Verify candidate ownership defensively
    is_authorized = (student.partner_id.id == user.partner_id.id)
    if not is_authorized and hasattr(student, 'parent_ids') and student.parent_ids:
        parent_partner_ids = student.parent_ids.mapped('user_id.partner_id.id')
        is_authorized = (user.partner_id.id in parent_partner_ids)
    elif not is_authorized and hasattr(student, 'parent_id') and student.parent_id:
        is_authorized = (user.partner_id.id == student.parent_id.id)

    if not is_authorized:
        raise Forbidden(_("You do not have permission to view this certification."))
```

## ⚠️ Pitfalls

- **Do NOT assume field names across OpenEduCat variants:** OpenEduCat Community and Enterprise have variations between `parent_id` (`res.partner`) and `parent_ids` (`op.parent`).
- **Never let authorization checks crash with 500:** Unhandled exceptions in authorization logic turn an intended HTTP 403 Forbidden into an HTTP 500 Internal Server Error, creating security monitoring noise and potential denial-of-service attack vectors.
- **Always write negative authorization tests:** Ensure test suites test unauthorized portal access asserting `Forbidden` (HTTP 403), not just happy path authorized downloads.

## Verification

Run an automated test simulating an unauthorized portal user downloading another student's certificate:

```python
from werkzeug.exceptions import Forbidden
from odoo.addons.website.tools import MockRequest

with MockRequest(env(user=unauthorized_portal_user)):
    with self.assertRaises(Forbidden):
        controller.portal_my_certificate_download(other_candidate_enrollment.id)
```

## References

- Related file: `security/portal-controller-sudo-browse-bypasses-record-rules-idor.md`
- Module: `openeducat_ghtc/controllers/portal.py`
