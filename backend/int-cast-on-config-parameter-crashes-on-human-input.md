# A bare int() on an ir.config_parameter Crashes the Whole Feature on Human-Typed Input

| Field         | Value        |
|---------------|--------------|
| Category      | backend      |
| Odoo Versions | All          |
| Severity      | 🔴 Critical  |
| Last Verified | 2026-08-05   |
| Author        | ENG/Gamal Mansour |

**Tags:** `ir.config_parameter`, `settings`, `robustness`, `valueerror`, `defensive-coding`

---

## Problem

Cash-flow forecasting aborted for **every project** with a raw Python traceback — no
user-facing message, no hint of what to fix:

```
File ".../construction_cashflow/models/cashflow.py", line 83, in action_compute_cashflow
    lag = int(self.env['ir.config_parameter'].sudo().get_param(
        'construction_cashflow.collection_lag_months', '1'))
ValueError: invalid literal for int() with base 10: '1 month'
```

The parameter had been set — perfectly reasonably — from Settings → Technical → System
Parameters:

```sql
SELECT key, value FROM ir_config_parameter WHERE key LIKE '%lag%';
-- construction_cashflow.collection_lag_months | 1 month
```

## Root Cause

`ir.config_parameter` values are **always free text typed by a human**. There is no field
type, no validation, no widget — the Settings form accepts any string. A user asked for
"months" writes `1 month`, `two`, `1.5`, or leaves it blank; all are natural entries.

The `default='1'` argument on `get_param()` gives false confidence: it only applies when the
key is **missing**, never when the key exists with a malformed value. So the code path that
looks safe (`get_param(key, '1')`) is exactly the one that explodes once anybody visits
Settings.

Because the cast sits at the top of the compute, one typo in an unrelated settings screen
takes down an entire business feature — and the traceback names Python, not the setting.

## Solution ✅

Do **not** patch the one file that crashed — the pattern is always copy-pasted. Extend
`ir.config_parameter` once, in the lowest common dependency of the suite, so every module
gets the guarded readers with no new dependency:

```python
# construction_approvals/models/ir_config_parameter.py
from itertools import takewhile

from odoo import models


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def get_param_int(self, key, default=0):
        """Read `key` as a whole number, degrading to `default` instead of raising."""
        text = str(self.sudo().get_param(key, '') or '').strip()
        negative = text.startswith('-')
        digits = ''.join(takewhile(str.isdigit, text.lstrip('+-')))
        if not digits:
            return default
        return -int(digits) if negative else int(digits)

    def get_param_float(self, key, default=0.0):
        """Read `key` as a float, degrading to `default` instead of raising."""
        text = str(self.sudo().get_param(key, '') or '').strip()
        head = ''.join(takewhile(lambda c: c.isdigit() or c in '.-+', text))
        try:
            return float(head)
        except ValueError:
            return default
```

Then migrate every call site — mechanical, and it reads better too:

```python
# before
days = int(self.env['ir.config_parameter'].sudo().get_param('mod.alert_days', 30))
# after
days = self.env['ir.config_parameter'].get_param_int('mod.alert_days', 30)
```

**Picking the host module:** walk the dependency graph to the lowest common ancestor of
every module that reads a numeric parameter. Here `construction_approvals` was reached by
all of them (four directly, `construction_cashflow` via `construction_project`), so nothing
needed a new `depends` entry. Putting the helper in a leaf module and adding dependencies
upward is how you create a dependency cycle.

Pin the behaviour with tests that feed it what users actually type:

```python
def test_02_human_typed_unit_does_not_crash(self):
    self.assertEqual(self._lag('1 month'), 1, "must read the leading number")

def test_04_garbage_falls_back_to_one(self):
    self.assertEqual(self._lag('two months'), 1,
                     "never abort the forecast over a configuration typo")
```

## ⚠️ Pitfalls

- `get_param(key, default)` only returns `default` when the key is **absent**. An existing
  key with an empty or malformed value still comes back as-is — guard the cast, not the read.
- Same trap applies to `float()`, `json.loads()`, and `int()` on `safe_eval` output.
- Grep the whole codebase, not just the file that crashed: the pattern is always copy-pasted.
  In this suite one crash led to **ten** identical latent crashers across five modules:
  `grep -rn "config_parameter" --include="*.py" . | grep -E "int\(|float\("`
- `get_param(key, default=12)` with a **numeric** default is a second smell: the fallback is
  an int but the stored value is always a string, so the two branches return different types.
- Do not "fix" this by correcting the row in the database — the next user retypes it. Harden
  the code; correcting the data is optional cleanup afterwards.
- If a bad value must be surfaced rather than silently defaulted, raise a `UserError` naming
  the parameter key and the offending value — never let a raw `ValueError` reach the user.

## Verification

```bash
# The exact human input that used to crash now yields 1
./odoo-bin -d <db> -u construction_cashflow --test-enable --stop-after-init
# 0 failed, 0 error(s)
```

## References

- Related file: `backend/env-su-guard-silently-passes-in-transactioncase.md`
- Related file: `backend/testing-projects-contract-constraints.md`
