# Adding Chatter in Odoo 17 & 18: Requirements, Syntax, and Pitfalls

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `chatter`, `mail.thread`, `mail.activity.mixin`, `views`, `odoo18`, `tracking`

---

## Problem

When creating custom models and form views, developers often omit the Chatter, or use legacy Odoo 16 `<div class="oe_chatter">` markup, or add `<chatter/>` in XML without inheriting `mail.thread` and adding `'mail'` to `depends`.

As a result:
- The form has no communication history, no audit trail for status/financial changes, and cannot schedule activities.
- If `<chatter/>` is placed inside `<sheet>`, layout breaks.
- If `'mail'` is not in `depends`, views crash with XML parsing errors on install.

## Root Cause

In Odoo 17 and 18:
1. **Simplified XML Syntax:** Odoo deprecated `<div class="oe_chatter">` and replaced it with a self-closing `<chatter/>` tag.
2. **Placement:** `<chatter/>` MUST be placed directly inside `<form>`, immediately after `</sheet>`.
3. **Model Inheritance:** The Python model must inherit both `mail.thread` (for messages & tracking) and `mail.activity.mixin` (for activities).
4. **Manifest Dependency:** The module's `__manifest__.py` MUST list `'mail'` in `depends`.

## Solution ✅

### 1. Python Model
```python
from odoo import models, fields

class CustomBusinessModel(models.Model):
    _name = 'custom.business.model'
    _description = 'Custom Business Model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
    ], default='draft', tracking=True)
```

### 2. XML Form View
```xml
<record id="view_custom_business_model_form" model="ir.ui.view">
    <field name="name">custom.business.model.form</field>
    <field name="model">custom.business.model</field>
    <field name="arch" type="xml">
        <form string="Custom Model">
            <header>
                <field name="state" widget="statusbar"/>
            </header>
            <sheet>
                <div class="oe_title">
                    <h1><field name="name"/></h1>
                </div>
                <!-- Form fields -->
            </sheet>
            <!-- In Odoo 17/18: chatter tag right below sheet -->
            <chatter/>
        </form>
    </field>
</record>
```

### 3. Manifest Dependency
In `__manifest__.py`:
```python
'depends': [
    'base',
    'mail',  # Mandatory for chatter and activity mixins
],
```

## ⚠️ Pitfalls

- **Do NOT place `<chatter/>` inside `<sheet>`**: It will render inside the white card container and break responsive sidebar layouts.
- **Never set `tracking=True` on `fields.Html`**: Odoo will install cleanly but raise `NotImplementedError` whenever a user saves changes to that record.
- **Missing `mail` dependency**: If the module installs before `mail`, server start fails with `KeyError: 'mail.thread'`.

## Verification

1. Upgrade the module: `odoo-bin -u custom_module -d db_name`.
2. Open any record form view.
3. Verify the right/bottom panel shows "Send message", "Log note", and "Activities".
4. Modify a field marked with `tracking=True` and save; verify a tracking entry appears in the message log.

## References

- Base Mail Chatter: `addons/mail/views/mail_activity_views.xml`
