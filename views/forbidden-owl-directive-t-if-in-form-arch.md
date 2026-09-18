# Forbidden owl directive used in arch (t-if) in Odoo 17/18 Form Views

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-18                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `owl`, `arch`, `t-if`, `invisible`, `form-view`, `parse-error`

---

## Problem

When upgrading or installing a module in Odoo 17, 18, or 19 with a standard form view (`ir.ui.view` with `<form>`), Odoo crashes during XML conversion with a `ParseError`:

```
odoo.tools.convert.ParseError: while parsing /path/to/module/views/my_view.xml:5
Error while validating view near:

    <div t-if="has_warning" class="alert alert-danger" role="alert">
        ⚠️ Warning message here
    </div>

Forbidden owl directive used in arch (t-if).
```

## Root Cause

Starting with Odoo 17 (and continuing in 18 and 19), Odoo strictly enforces view arch syntax. Standard form and tree views are not QWeb templates (except inside `<kanban>` or `<t t-name="card">`). 

Directives like `t-if`, `t-elif`, `t-else`, or `t-esc` are prohibited directly on standard HTML elements (like `<div>`, `<span>`, `<p>`) inside a form view `<sheet>`.

## Solution ✅

Use the standard Odoo 17+ Python-like conditional modifier `invisible="..."` on the HTML tag instead of `t-if`:

### Incorrect ❌
```xml
<div t-if="has_warning" class="alert alert-danger py-1 px-2 mb-0 small" role="alert">
    ⚠️ Critical defects present — Handover blocked until repaired!
</div>
```

### Correct ✅
```xml
<!-- Ensure the field is present in the form view so its value exists in the web client model state -->
<field name="has_warning" invisible="1"/>

<div invisible="not has_warning" class="alert alert-danger py-1 px-2 mb-0 small" role="alert">
    ⚠️ Critical defects present — Handover blocked until repaired!
</div>
```

## ⚠️ Pitfalls

1. **Forgetting to include the trigger field in the view**:
   When using `invisible="not has_warning"` on a plain `<div>`, if `<field name="has_warning" invisible="1"/>` is not declared anywhere inside the `<form>`, the client might not evaluate the expression correctly or may assume False. Always place the boolean field inside `<sheet>` (hidden via `invisible="1"`).
2. **QWeb templates vs Form Views**:
   `t-if` is fully valid inside `<template>` (QWeb reports and website controllers) and inside `<t t-name="card">` within Kanban views. It is ONLY forbidden inside standard `<form>` and `<list>` view archs.

## Verification

Run XML parsing or upgrade the module:
```bash
python3 odoo-bin -c odoo.conf -u my_module
```
The view will validate without `Forbidden owl directive used in arch (t-if)`.
