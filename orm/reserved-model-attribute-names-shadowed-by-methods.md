# A method named `_register` (or other reserved model attrs) silently becomes a bool → "'bool' object is not callable"

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `models`, `reserved`, `_register`, `metaclass`, `naming`

---

## Problem

A helper method named `_register` on a model looks fine and even installs, but
calling it explodes at runtime:

```python
class ActivityDevice(models.Model):
    _name = 'activity.device'
    def _register(self, partner, device_id, token=None):   # BAD name
        ...
```

```python
env['activity.device']._register(partner, 'dev-x', token='a')
# TypeError: 'bool' object is not callable
```

`_register` resolves to `True`, not your function.

## Root Cause

`_register` is a **reserved Odoo model attribute**: `models.BaseModel._register`
is a class-level boolean (default `True`) that the model metaclass reads to decide
whether the model is added to the registry (abstract/base classes set
`_register = False`). Defining a method with that name puts a *function* where the
framework expects a *bool*; the metaclass / inheritance machinery ends up with the
bool value winning, so `self._register` is `True` at call time.

The same trap applies to any reserved dunder-less model attribute the framework
owns, e.g. `_name`, `_inherit`, `_inherits`, `_auto`, `_abstract`, `_transient`,
`_table`, `_sequence`, `_order`, `_rec_name`, `_description`, `_sql_constraints`,
`_log_access`, `_check_company_auto`, `_parent_name`, `_fold_name`.

## Solution ✅

Name custom methods with a distinctive, action-specific prefix that can't collide:

```python
def _register_device(self, partner, device_id, token=None):
    ...
```

Good habit: give model service methods a verb+noun name tied to the model
(`_register_device`, `_issue_token`, `_notify`, `_gc_logs`) rather than a bare
framework-ish verb.

## ⚠️ Pitfalls

- It **installs cleanly** — the model still loads (default `_register` is `True`),
  so nothing fails until the method is actually called. Static review won't catch
  it; a unit test that calls the method will.
- The error message (`'bool' object is not callable`) names neither your method
  nor `_register`, so it's easy to misdiagnose. If a model method suddenly "is a
  bool", check its name against the reserved list.
- `_register_hook` is a real ORM hook and is fine to override — only the bare
  `_register` is the reserved bool.

## Verification

```bash
odoo-bin -c conf -d db -u <module> --test-enable --test-tags /<module> \
  --stop-after-init --http-port 8911 --gevent-port 8912 --max-cron-threads=0
# a test that calls the method must pass (installing alone won't surface it)
```

## References

- Code: `activity/activity_notification/models/activity_device.py` (`_register_device`)
- Related file: `orm/field-name-collision-with-mail-activity-mixin.md`
