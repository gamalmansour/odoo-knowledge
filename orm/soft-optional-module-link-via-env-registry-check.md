# Soft Link to an Optional Module: Check the Model Registry at Runtime Instead of Adding a Dependency

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟢 Low                                     |
| Last Verified | 2026-08-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `depends`, `optional-module`, `cross-module`, `env`, `soft-link`

---

## Problem

A feature in module A would be better with data from module B, but B is optional (e.g. a billing-schedule generator in `construction_contract` that can weight periods by the cash-flow forecast from `construction_cashflow` — which itself depends on A, so a manifest dependency would be circular anyway).

## Root Cause

`depends` is all-or-nothing: adding B to A's manifest forces every installation to carry B (or is outright circular). Referencing `self.env['b.model']` unconditionally raises `KeyError` when B is absent.

## Solution ✅

Gate the integration on the model registry and fail with a *helpful* message:

```python
if 'construction.cashflow.line' not in self.env:
    raise UserError(_(
        "The Cash-Flow module (construction_cashflow) is not installed — "
        "use Linear or S-Curve instead."))
lines = self.env['construction.cashflow.line'].search([...])
```

`'model.name' in self.env` is True only when the module defining the model is installed in THIS database — it is the supported runtime capability check.

## ⚠️ Pitfalls

- Only Python may soft-link. **XML views/data cannot** reference the optional module's fields or xmlids — that still needs a real dependency or a bridge module.
- Offer a working fallback (here: linear / S-curve) — a feature that only errors without the optional module is a dependency in disguise.
- Do not probe with `hasattr(record, 'field')` for optional *fields* added by B on A's models; prefer `'field' in record._fields`.
- Test BOTH branches: with B absent the error path, with B present the data path.
- **When your validate/CI run always installs A+B together** (e.g. B is a
  hard prerequisite of a sibling module you also test, so a real "B absent"
  install never happens in that run), the absent branch still needs direct
  coverage — don't settle for "it's covered by whichever install shape CI
  happens to run". Pop the model out of the live registry for the duration
  of one assertion and restore it automatically:
  ```python
  from unittest.mock import patch
  with patch.dict(self.env.registry.models, clear=False):
      del self.env.registry.models['b.model']
      self.assertEqual(my_guarded_call(), fallback_value)  # exercises the branch itself
  # original registry state is restored here, even though we mutated it in-place
  ```
  `patch.dict` snapshots the dict on enter and restores the *original*
  contents on exit regardless of what you mutate inside the `with` block —
  so `del`-ing a key still rolls back cleanly. This proves the guard branch
  actually returns the fallback (not a `KeyError`/500) rather than merely
  proving "no B-owned rows exist yet", which is a weaker, easy-to-fool
  substitute. Keep the mocked block to ONE guarded call — the same request
  path must not need any other B-owned model in that window, or you will
  break something unrelated instead of testing the guard.

## References

- Implemented in `construction_contract` v17.0.1.11.0 — `wizard/generate_billing_periods_wizard.py` (`cashflow` distribution method)
