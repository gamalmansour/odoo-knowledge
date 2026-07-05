---
title: "Odoo 19 Upgrade: res.groups and ir.actions.server xml field changes"
date: "2026-07-05"
category: "upgrade"
tags:
  - "Odoo 19"
  - "Security"
  - "res.groups"
  - "ir.actions.server"
  - "category_id"
  - "groups_id"
---

# Odoo 19 Upgrade: res.groups and ir.actions.server xml field changes

## Problem Description
When upgrading custom modules to Odoo 19, parsing errors occur in XML files that define `res.groups` and `ir.actions.server` records:

1. `ValueError: Invalid field 'category_id' in 'res.groups'`
2. `ValueError: Invalid field 'groups_id' in 'ir.actions.server'`

## Cause
In Odoo 19:
- `res.groups` no longer has a `category_id` field. Group categorization has been changed/removed from the model.
- `ir.actions.server` renamed the `groups_id` Many2many field to `group_ids` to comply with Odoo naming conventions for pluralized Many2many fields.

## Solution ✅
1. For `res.groups`, remove the `<field name="category_id" ref="..."/>` line from the group definitions in XML files.
2. For `ir.actions.server`, rename `<field name="groups_id" .../>` to `<field name="group_ids" .../>`.

## ⚠️ Pitfalls
- Forgetting to rename `groups_id` in action bindings will cause the database initialization to fail entirely.
- Attempting to keep `category_id` will crash module installation.

## Versions
- Odoo 19
