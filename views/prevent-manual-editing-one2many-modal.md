# Prevent Manual Editing via One2many Modal Form

**Tags:** `views`, `one2many`, `readonly`, `ui`, `modal`

## 📝 Background Context
When displaying a One2many list view inside a form view, developers often use `create="false" edit="false" delete="false"` on the `<list>` (or `<tree>`) node to prevent users from adding, editing inline, or deleting records from the list.

## ⚠️ The Pitfall
Even with `edit="false"` on the list node, if a user clicks on an existing line item, Odoo will open the default modal form for that record. If the `<field>` itself isn't marked as `readonly`, and the underlying model's form view doesn't restrict fields, the user can modify field values inside the modal and save them, effectively bypassing the `edit="false"` restriction that was intended to protect the list.

## ✅ The Solution
To completely block manual UI editing for the entire relation (both inline and via the modal form), apply `readonly="1"` directly to the `<field>` definition, not just the list view attributes.

```xml
<!-- INCORRECT: Leaves the modal form vulnerable to edits -->
<field name="approval_ids">
    <list create="false" edit="false" delete="false">
        <field name="state"/>
    </list>
</field>

<!-- CORRECT: Blocks both inline editing and modal form editing -->
<field name="approval_ids" readonly="1">
    <list create="false" edit="false" delete="false">
        <field name="state"/>
    </list>
</field>
```

Applying `readonly="1"` to the field ensures the whole relation is read-only from the current view. Note that this is a UI-level restriction; backend python logic (e.g., button actions) can still write to the relation.

## ⚠️ It is worse than the modal on mobile

A one2many is rendered by up to THREE sub-views in the same form — `<list>`,
the `<form>` dialog, and a `<kanban class="o_kanban_mobile">`. A modifier
written against one of them does not exist in the others, and a phone uses the
kanban and the dialog, never the list. A `readonly` set in Studio (which writes
its xpath against the list it can see) is therefore absent on mobile entirely.

And none of it is security: a view modifier is a hint to the browser, so an API
key or an Excel import writes the field regardless. When the point is to stop
somebody changing a value — not merely to tidy the UI — enforce it in
`create`/`write` on the model and keep the modifier as courtesy. Full recipe:
[one2many-subview-modifiers-miss-the-mobile-surfaces.md](one2many-subview-modifiers-miss-the-mobile-surfaces.md)

