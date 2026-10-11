# `dict(record._fields['x'].selection)` Crashes on Related Selection Fields — the Attribute Is a Resolver Function

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `selection`, `related`, `_fields`, `TypeError`, `labels`

---

## Problem

Building a human label for a selection value in an error message:

```python
state=dict(contract._fields['state'].selection).get(contract.state)
```

works on ordinary selection fields but crashes on a **related** selection field:

```
TypeError: 'function' object is not iterable
```

## Root Cause

On a related selection field (e.g. `contract.owner.state = fields.Selection(related='stage_id.contract_state')`), the field object's `.selection` attribute is **not a list of tuples** — it is the resolver *function* Odoo uses to fetch the selection from the source field. Only fields that declare their own literal list carry one.

## Solution ✅

Either read the labels from the **source field**:

```python
labels = dict(self.env['contract.stage']._fields['contract_state'].selection)
```

or use the API that resolves both cases (returns translated labels too):

```python
labels = dict(record._fields['state']._description_selection(record.env))
```

`_description_selection(env)` is the safer default: it works for literal lists, related fields, and callable selections, and applies the user's language.

## ⚠️ Pitfalls

- The crash only fires when the error path runs, so it hides behind happy-path tests — assert your error messages in tests (that is exactly how this one surfaced).
- The literal-list `dict(...)` shortcut also returns **untranslated** source strings; `_description_selection` is translation-aware.

## Verification

Trigger the error path in a test and assert the message renders (no TypeError).

## References

- Hit in `construction_contract` v17.0.1.9.0 `_apply_payment_method_gate` (`contract.owner.state` is related to `stage_id.contract_state`)
