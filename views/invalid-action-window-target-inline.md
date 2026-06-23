---
category: "Views"
title: "Invalid value for ir.actions.act_window.target: 'inline'"
tags:
  - "Views"
  - "res.config.settings"
  - "ir.actions.act_window"
  - "Target Inline"
  - "Error"
odoo_version: "19.0"
---

# Problem Context
When defining a menu item and window action for `res.config.settings` (Configuration -> Settings), using `<field name="target">inline</field>` in Odoo 19 causes an `RPC_ERROR` / `ValueError` during module installation or upgrade.

```python
ValueError: Wrong value for ir.actions.act_window.target: 'inline'
```

# Solution ✅
Remove the `<field name="target">inline</field>` line from the `ir.actions.act_window` record.

By default, Odoo window actions will use the `current` target, and `res.config.settings` views function correctly without specifying `target="inline"` in recent Odoo versions (18.0 / 19.0).

# ⚠️ Pitfalls
* Assuming `inline` is valid for settings because it was used in much older Odoo versions.
* Getting blocked during module installation/upgrade with an unhandled exception pointing to `convert.py`.

# Example Fix

**Before (Fails):**
```xml
<record id="action_ss_trade_marketing_config_settings" model="ir.actions.act_window">
    <field name="name">Settings</field>
    <field name="res_model">res.config.settings</field>
    <field name="view_mode">form</field>
    <field name="target">inline</field>
    <field name="context">{'module' : 'ss_trade_marketing'}</field>
</record>
```

**After (Works):**
```xml
<record id="action_ss_trade_marketing_config_settings" model="ir.actions.act_window">
    <field name="name">Settings</field>
    <field name="res_model">res.config.settings</field>
    <field name="view_mode">form</field>
    <field name="context">{'module' : 'ss_trade_marketing'}</field>
</record>
```
