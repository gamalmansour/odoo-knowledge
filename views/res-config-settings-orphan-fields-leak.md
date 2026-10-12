# Settings Section Visible in All Modules Due to Direct XPath Form Injection in Odoo 17/18

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `res.config.settings`, `views`, `owl`, `xpath`, `settings`, `hr_attendance`

---

## Problem

A custom settings section (e.g. Attendance Overtime/Late rules, custom counters, or integration credentials) unexpectedly displays at the very top (or bottom) of the Settings page across **all** modules (General Settings, Sales, Invoicing, Project, Inventory), regardless of which app is selected from the left settings sidebar navigation.

```
Settings page displays:
[Attendance]
Ot Hours (Draft): 0
Ot Hours (Logged): 0
Late Hours (Draft): 0.00
Late Hours (Logged): 0.00
Date Counter: 0
Logged Counter: 0
In Review Counter: 0
(Rendered permanently above or outside active module settings)
```

## Root Cause

In Odoo 17 and 18, `res.config.settings` is entirely powered by OWL components (`SettingsApp`, `SettingsContainer`). The settings client renders navigation tabs on the left for each `<app name="...">` block. When switching apps, OWL toggles visibility based on `<app>` tags.

When legacy code inherits `base.res_config_settings_view_form` and uses:
```xml
<xpath expr="//form" position="inside">
    <h2>Attendance</h2>
    <div class="row mt16 o_settings_container">
        ...
    </div>
</xpath>
```
The injected XML elements are placed directly under the root `<form>` outside of any `<app>` container. Because they are orphan root nodes without an enclosing `<app>` tag, OWL never hides them during tab switching, causing them to leak into every single settings panel.

## Solution ✅

### Scenario A: Injecting settings into an existing application (e.g. Attendances)
Target the existing `<app>` tag using modern Odoo 18 `<block>` and `<setting>` tags:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="id_res_config_settings_view_form_inherit" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.attendance.rules</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="hr_attendance.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//app[@name='hr_attendance']" position="inside">
                <block title="Attendance Rules &amp; Counters" name="attendance_custom_rules_setting_container">
                    <setting string="Ot Hours (Draft)" help="Allowed draft overtime hours.">
                        <field name="ot_hours"/>
                    </setting>
                    <setting string="Ot Hours (Logged)" help="Overtime hours for logged attendances.">
                        <field name="ot_hours_logged"/>
                    </setting>
                    <setting string="Late Hours (Draft)" help="Allowed draft late hours.">
                        <field name="late_hours"/>
                    </setting>
                    <setting string="Late Hours (Logged)" help="Allowed logged late hours.">
                        <field name="late_hours_logged"/>
                    </setting>
                    <setting string="Date Counter" help="Number of days for attendance counter.">
                        <field name="date_counter"/>
                    </setting>
                    <setting string="Logged Counter" help="Threshold hours for logged attendance validation.">
                        <field name="logged_counter"/>
                    </setting>
                    <setting string="In Review Counter" help="Threshold counter for attendance in-review status.">
                        <field name="in_review_counter"/>
                    </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

### Scenario B: Adding a new standalone app tab to Settings
Wrap the configuration inside an `<app>` tag:

```xml
<xpath expr="//form" position="inside">
    <app data-string="My Module" string="My Module" name="my_module_name">
        <block title="Configuration" name="my_module_config">
            <setting string="Option 1">
                <field name="option_1"/>
            </setting>
        </block>
    </app>
</xpath>
```

## ⚠️ Pitfalls

- **Do NOT add classes to `<app>` in Odoo 18:** Adding `class="app_settings_block"` to `<app>` causes an unhandled Owl error (`Unknown Key 'class' in SettingsApp`).
- **Database View Cache:** Changing the XML on disk does not immediately update the browser if the view in `ir_ui_view` is cached. You must upgrade the module (`-u <module_name>`) to push the updated arch into PostgreSQL.
- **Ensure Proper Dependencies:** If xpathing `//app[@name='hr_attendance']` or inheriting `hr_attendance.res_config_settings_view_form`, ensure `'hr_attendance'` is declared in `'depends'` in `__manifest__.py`.

## Verification

1. Open Odoo Settings.
2. Select **General Settings**, **Sales**, or **Invoicing**: Verify the custom section does NOT appear.
3. Select **Attendances**: Verify the section appears cleanly under its own block title.

## References

- Related: `views/res-config-settings-app-class-owl-error.md`
