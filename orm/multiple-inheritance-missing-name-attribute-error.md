# Multiple Model Inheritance Missing `_name` Attribute Causes `ValueError: The _name attribute ClassName is not valid`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-17                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `inheritance`, `_inherit`, `_name`, `mail.activity.mixin`, `ValueError`

---

## Problem

When inheriting a model along with a mixin (e.g. `mail.activity.mixin` or `mail.thread`) using a list in `_inherit` without explicitly specifying `_name`, Odoo crashes during registry loading:

```text
ValueError: The _name attribute OpBatch is not valid.
2026-11-16 23:09:10,244 40128 CRITICAL openedu17_community odoo.service.server: Failed to initialize database `openedu17_community`. 
Traceback (most recent call last):
  File "/Users/gamal/odoo/odoo17.0/odoo/models.py", line 3141, in _auto_init
    raise_on_invalid_object_name(self._name)
  File "/Users/gamal/odoo/odoo17.0/odoo/models.py", line 133, in raise_on_invalid_object_name
    raise ValueError(msg)
ValueError: The _name attribute OpBatch is not valid.
```

## Root Cause

In Odoo ORM, when `_inherit` is a single string (e.g. `_inherit = 'op.batch'`), Odoo automatically sets `_name = _inherit` if `_name` is omitted. However, when `_inherit` is a list (e.g. `_inherit = ['op.batch', 'mail.activity.mixin']`), Odoo defaults `_name` to the Python class name (in this case `'OpBatch'`).

Because Odoo model names must be lowercase and dot-separated, `raise_on_invalid_object_name` detects capital letters and aborts server initialization.

## Solution ✅

Always explicitly specify `_name` whenever `_inherit` is a list of models:

```python
from odoo import models

class OpBatch(models.Model):
    _name = 'op.batch'
    _inherit = ['op.batch', 'mail.activity.mixin']
```

## ⚠️ Pitfalls

- **Single vs Multiple Inheritance:** Omitting `_name` works when `_inherit` is a single string, which often creates the false impression that `_name` is always optional in extension models.
- **Delegation Inheritance:** Similarly, when using `_inherits = {'res.partner': 'partner_id'}`, ensure `name` is populated (or defaulted) before saving, as PostgreSQL check constraint `res_partner_check_name` rejects records with empty names.

## Verification

Run the Odoo server with module upgrade and ensure registry initializes cleanly without `ValueError: The _name attribute ... is not valid`.
