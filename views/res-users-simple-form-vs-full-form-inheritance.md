# Res.Users View Inheritance: view_users_simple_form vs view_users_form

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19, All                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `res.users`, `views`, `inheritance`, `view_users_form`, `view_users_simple_form`

---

## Problem

When developers inherit `res.users` to display custom fields (such as commission rates, lead distribution filters, or approval hierarchies), they often inherit `base.view_users_simple_form` because it appears in relational pop-ups, employee cards, or quick-create dialogs.

However, when administrators open the user from **Settings -> Users & Companies -> Users** (`base.view_users_form`), the custom fields are completely missing from the form view!

```
Symptom: Fields appear when opening a user from a quick relational dialog,
but disappear entirely when navigating to Settings -> Users.
```

## Root Cause

Odoo provides two distinct form views for `res.users`:
1. `base.view_users_simple_form` (Priority 1): A compact, simplified form view used by default for modal dialogs, invitations, and quick editing.
2. `base.view_users_form` (Default Priority 16): The primary, full-featured administration view containing notebooks, access rights, and preferences.

Inheriting only `base.view_users_simple_form` leaves the primary view untouched. Conversely, inheriting only `base.view_users_form` leaves modal popups without the fields.

## Solution ✅

When extending `res.users` with business or operational fields:
1. Always inherit `base.view_users_form` so administrators can configure fields from **Settings -> Users**. Group them logically (e.g. inside a new page or under Preferences).
2. If the fields must also be accessible during quick editing / dialogs, inherit `base.view_users_simple_form` as a secondary view.

```xml
<!-- 1. Primary Full Form View (Settings -> Users) -->
<record id="view_users_form_inherit_crm_ext" model="ir.ui.view">
    <field name="name">res.users.form.inherit.crm.ext</field>
    <field name="model">res.users</field>
    <field name="inherit_id" ref="base.view_users_form"/>
    <field name="arch" type="xml">
        <xpath expr="//notebook" position="inside">
            <page string="Sales &amp; Commissions" name="sales_commissions">
                <group>
                    <group string="Commission Details">
                        <field name="job_id"/>
                        <field name="personal"/>
                        <field name="cut"/>
                    </group>
                    <group string="Lead Allocation">
                        <field name="assignment_domain" widget="domain" options="{'model': 'crm.lead'}"/>
                        <field name="assignment_optout"/>
                    </group>
                </group>
            </page>
        </xpath>
    </field>
</record>

<!-- 2. Simplified Form View (Dialogs & Popups) -->
<record id="view_users_simple_form_inherit_crm_ext" model="ir.ui.view">
    <field name="name">res.users.simple.form.inherit.crm.ext</field>
    <field name="model">res.users</field>
    <field name="inherit_id" ref="base.view_users_simple_form"/>
    <field name="arch" type="xml">
        <xpath expr="//sheet" position="inside">
            <group string="Sales &amp; Commissions">
                <field name="job_id"/>
                <field name="personal"/>
                <field name="cut"/>
            </group>
        </xpath>
    </field>
</record>
```

## ⚠️ Pitfalls

- **Avoid dumping fields directly into `//sheet` of `base.view_users_form`**: The main form uses a structured notebook; placing unbounded groups inside `//sheet` can break layout responsiveness. Use `<xpath expr="//notebook" position="inside">` instead.
- **Data Inconsistency**: If fields are editable in both views, ensure model-level validations or defaults are on the model, not on view widgets.

## Verification

1. Open **Settings -> Users & Companies -> Users** -> Click any user -> Confirm the new page/fields are visible.
2. Open a relational Many2one pointing to `res.users` and click "Open Record" or "External Link" -> Confirm the simplified view renders correctly.

## References

- Base Users Form: `addons/base/views/res_users_views.xml`
