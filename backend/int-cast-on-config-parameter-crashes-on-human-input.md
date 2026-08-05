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

Wrap every config-parameter cast in a tolerant helper that degrades to the default instead
of raising:

```python
from itertools import takewhile

def _collection_lag_months(self):
    """Collection lag in whole months, read defensively from system parameters.

    ir.config_parameter values are free text a human types in Settings, so a
    perfectly natural entry like "1 month" (or a blank, or "two") used to reach a
    bare int() and abort the WHOLE cash-flow forecast with a raw Python ValueError.
    Pull the leading integer out, and fall back to 1 month rather than break the
    forecast over a configuration typo.
    """
    raw = self.env['ir.config_parameter'].sudo().get_param(
        'construction_cashflow.collection_lag_months', '1')
    digits = ''.join(takewhile(str.isdigit, (str(raw) or '').strip()))
    return int(digits) if digits else 1
```

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
- Grep the whole codebase, not just the file that crashed: the pattern is usually copy-pasted.
  `grep -rn "int(self.env\['ir.config_parameter'\]" .`
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
