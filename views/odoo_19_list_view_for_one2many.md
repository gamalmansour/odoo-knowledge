# Using `<list>` instead of `<tree>` for One2many inline views in Odoo 19+

**Category:** Backend / Views
**Odoo Versions:** 17.0, 18.0, 19.0+
**Last Verified:** 2026-07-01

## Problem ❌
In Odoo 19, when defining a form view that includes a One2many field, using the older `<tree>` tag inside the `<field>` definition can lead to an XML ParseError complaining that a field (e.g. `product_id`) does not exist on the *parent* model (the model containing the One2many field). This happens because Odoo's view parser may fail to switch context to the child model when `<tree>` is used instead of `<list>`.

Example of what causes the error:
```xml
<field name="line_ids">
    <tree editable="bottom">
        <field name="product_id"/> <!-- Error: Field product_id does not exist in the parent model -->
    </tree>
</field>
```

## Solution ✅
Use `<list>` instead of `<tree>` for inline list views inside One2many/Many2many fields. Starting from Odoo 16, Odoo began migrating from `tree` to `list`, and in Odoo 19+, the parser strictly expects `<list>` inside a field definition, or at least handles it correctly.

```xml
<field name="line_ids">
    <list editable="bottom">
        <field name="product_id"/>
    </list>
</field>
```

## ⚠️ Pitfalls
* If you see an error like `Field "X" does not exist in model "Y"` where Y is the parent model and X is a field of the child model, immediately check if you are using `<tree>` instead of `<list>`.
* While standalone views can still be `<record type="ir.ui.view"> ... <tree>` or `<list>`, for inline definitions inside a form view `<field>`, the `<list>` tag is safer.
