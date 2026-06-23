---
title: OWL ListRenderer Crash with sum Attribute on Many2many Fields
description: Using sum attribute inside a list view for a Many2many field causes an OWL crash in the client.
category: views
tags: owl, views, many2many, sum, crash, list
versions: 17, 18, 19
---

# ⚠️ OWL ListRenderer Crash with `sum` Attribute on Many2many Fields

## ❌ The Problem
When displaying a `Many2many` field as a list inside a form view, adding the `sum="..."` attribute to any column (e.g., `amount_total`) causes a fatal crash in the frontend:
```text
UncaughtPromiseError > OwlError
TypeError: Cannot read properties of undefined (reading 'id') at ListRenderer.computeAggregates
```

### 🔍 Root Cause
Odoo's `ListRenderer` in OWL attempts to calculate the aggregates on the client side. However, for `Many2many` fields (especially computed ones), the record dataset is not always fully loaded in the expected state with stable `id`s during the compute aggregates phase, causing the JS engine to try and read `.id` on an undefined record.

## ✅ The Solution
**Remove the `sum` attribute** from the field inside the `Many2many` list view.

### 🔴 Bad Code
```xml
<field name="sale_order_ids" readonly="1">
    <list string="Sale Orders">
        <field name="name"/>
        <field name="amount_total" sum="Total"/> <!-- CRASHES HERE -->
    </list>
</field>
```

### 🟢 Good Code
```xml
<field name="sale_order_ids" readonly="1">
    <list string="Sale Orders">
        <field name="name"/>
        <field name="amount_total"/> <!-- Safely removed the sum attribute -->
    </list>
</field>
```

> **Pro Tip:** If you absolutely need the total sum of a `Many2many` field displayed in the form, create a separate computed `Float` or `Monetary` field on the main model and display it below the `Many2many` field, rather than trying to use the list view's aggregate feature.
