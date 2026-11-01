# OWL Form View Crash on Kanban Navigation

**Severity:** 🔴 Critical
**Tags:** `owl`, `kanban`, `form`, `crash`, `invisible`

**Category:** Frontend / Views
**Odoo Versions:** V16, V17, V18, V19
**Last Verified:** 2026-05-21

## Problem
When a user clicks on a record in a Kanban view to open the Form view, the Form view UI may appear completely blank, fail to render fields, or require a manual page refresh to load. 

## Cause
This is a known behavior in Odoo's OWL framework. If the Form view uses fields in `invisible` or `readonly` modifiers (e.g., `<field name="my_field" invisible="not show_my_field"/>`), and those dependency fields (like `show_my_field`) are **not** present in the Kanban view, the OWL form controller fails to evaluate the modifier during the initial transition because the data isn't cached from the Kanban state. This causes a rendering crash.

## Solution ✅
You must explicitly declare all fields used in Form view modifiers inside the Kanban view (as invisible fields).

```xml
<record id="my_model_kanban_view" model="ir.ui.view">
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <kanban>
            <!-- Add the missing dependency fields here -->
            <field name="show_my_field"/>
            <field name="is_locked"/>
            <templates>
                ...
            </templates>
        </kanban>
    </field>
</record>
```

## ⚠️ Pitfalls
- Adding the fields as `<field name="show_my_field" invisible="1"/>` in the Form view is NOT enough. They must be inside the `<kanban>` tag of the Kanban view so they are pre-fetched by the ORM before transitioning to the Form view.
