---
title: "QWeb Float Inputs and Python Portal Controllers - Handling Empty Values"
category: "views"
tags: ["qweb", "portal", "python", "float", "ui"]
date: "2026-06-28"
---

# QWeb Float Inputs and Python Portal Controllers - Handling Empty Values

## ⚠️ Problem Context

In portal views, Odoo developers often use HTML `<input type="number">` fields for numeric data like quantities, prices, etc. 
By default, if you use `t-att-value="line.qty"`, and `line.qty` is `0.0`, QWeb renders it as `value="0.0"`. Similarly, developers sometimes hardcode `value="0"`.

This creates friction for users on mobile or desktop because they must manually delete the `0` before typing their intended number. If they simply click and type `5`, the input becomes `05` or `0.05` instead of `5`.

To fix this UX issue, developers replace `value="0"` with `value=""` or use `t-att-value="line.qty or ''"`. This successfully renders an empty input field. 

**However, this causes a major crash in the Python backend:**
When the form is submitted with empty values, `request.httprequest.form.get('qty')` returns `""` (empty string). When Python attempts to parse this using `float(kw.get('qty'))`, it throws a `ValueError: could not convert string to float: ''`. If this is wrapped in a generic `try: ... except ValueError: pass` block (which is common in portal controllers), the record is silently NOT updated!

## ✅ Solution

### 1. In QWeb (Frontend)
Use the `or ''` fallback in `t-att-value` and remove hardcoded `value="0"`.

```xml
<!-- WRONG -->
<input type="number" t-att-value="line.qty"/>
<input type="number" value="0"/>

<!-- CORRECT -->
<input type="number" t-att-value="line.qty or ''"/>
<input type="number" value=""/>
```

### 2. In Python Portal Controllers (Backend)
When receiving the `kw` dictionary or `getlist` array, always handle empty strings by defaulting to `0.0` before casting to float.

```python
# WRONG (Crashes on empty string)
qty = float(kw.get('qty'))
qty = float(kw['qty'])

# WRONG (Silently ignores the update if the user deliberately emptied the field)
try:
    qty = float(kw.get('qty'))
except ValueError:
    pass 

# CORRECT
# If kw.get('qty') is '', '' or 0.0 evaluates to 0.0. float(0.0) is safe.
qty = float(kw.get('qty') or 0.0)
```

## 🚨 Pre-mortem Analysis / 6-Month Failure Simulation

If this is not handled properly:
- **6 Months Later:** The users are frustrated by having to delete `0` every time. They ask you to empty the default value. You empty it in QWeb.
- **The Crash:** The users submit forms leaving some fields blank. The backend throws a ValueError or silently skips updating those records. Data gets out of sync, leading to incorrect inventory or pricing.
