# Percentage Widget Multiplies Value by 100 (Ratio Behavior)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                   |
| Last Verified | 2026-07-06                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `widget`, `percentage`, `computation`, `ui`

---

## Problem

> When applying `widget="percentage"` to a `Float` or `Integer` field in Odoo views, the displayed value is 100 times larger than the stored value. For example, if the backend returns `50.0` (meaning 50%), the UI displays `5000%`.

## Root Cause

> The `percentage` widget in Odoo expects the backend value to be a decimal ratio (from `0.0` to `1.0`), not a pre-multiplied percentage (from `0` to `100`). It automatically multiplies the backend value by 100 before adding the `%` sign in the UI. 

## Solution ✅

> Ensure that the computed field or stored field in the Python backend returns the mathematical ratio instead of the percentage. Do not multiply by 100 in the `compute` method.

**Incorrect Backend (Python):**
```python
# This will cause the widget to show 5000% instead of 50%
record.progress_percentage = (completed / total) * 100.0
```

**Correct Backend (Python):**
```python
# The widget will multiply this by 100 and correctly show 50%
record.progress_percentage = completed / total
```

**View (XML):**
```xml
<field name="progress_percentage" widget="percentage" />
```

## ⚠️ Pitfalls

- **Conditional logic (e.g. `decoration-danger`):** Since the backend value is a ratio, view decorators must check against the ratio, not the percentage. For example, use `decoration-danger="progress_percentage &gt; 1.0"` instead of `&gt; 100`.
- **Database Storage:** Be careful if this field is used elsewhere (e.g., printed reports or custom integrations that don't use the widget). The raw value in the database will be `0.5`, not `50.0`.

## Verification

> Open the form or tree view containing the field. Verify that a 50% completion correctly displays as `50%` in the UI and that no backend errors are thrown due to zero division.
