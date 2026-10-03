# 🎨 Migrating invisible to column_invisible in Tree/List Views (Odoo 17 & 18)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-03                                 |
| Author        | ENG/Mohamed Saber                          |

**Tags:** `views`, `tree`, `list`, `invisible`, `column_invisible`, `xml`, `owl`, `evalColumnInvisible`

---

## Problem

In Odoo 17 and 18, using the `invisible="..."` attribute directly on `<field>` elements within a `<tree>` or `<list>` view does not hide the entire column. Instead, it hides only the cell value, leaving empty slots in the table layout. In some cases, it can trigger UI glitches or layout misalignment.

## Root Cause

Odoo 17 introduced a clean separation of layout visibility:
- **`invisible`**: Used on fields within Form views (hides the field widget) or on buttons/groups inside List/Form views.
- **`column_invisible`**: A dedicated attribute introduced for `<field>` elements in `<tree>` or `<list>` views to hide the entire column dynamically or statically.

## Solution ✅

Replace the `invisible` attribute with `column_invisible` for `<field>` elements defined inside `<tree>` or `<list>` tags.

### Before

```xml
<tree>
    <field name="some_id" invisible="1"/>
    <field name="display_name"/>
</tree>
```

### After

```xml
<tree>
    <field name="some_id" column_invisible="1"/>
    <field name="display_name"/>
</tree>
```

> **Note:** If dynamically showing/hiding a column based on a parent/context field in an embedded one2many/many2many subview inside a Form, use the `parent` prefix:
> `column_invisible="parent.some_parent_field == 'value'"`

## ⚠️ Pitfalls

- **Do NOT reference record fields in `column_invisible` in top-level `<list>` / `<tree>` views:**
  In a standalone top-level list view (e.g., opened via a menu action `view_mode="list,form"`), the ListRenderer evaluates `column_invisible` against `this.props.list.evalContext`, which contains only `context` (there is NO `record` and NO `parent`).
  Writing `column_invisible="not is_saudi_market"` on a column will crash the client with:
  `OwlError: Can not evaluate python expression: (bool(not is_saudi_market)) Error: Name 'is_saudi_market' is not defined` at `ListRenderer.evalColumnInvisible`.
  **Rule:** For optional, regional, or situational columns in top-level list views, use `optional="hide"` (or check `context.get(...)`), NEVER dynamic record field conditions.
- **Do NOT rename invisible on buttons:** Buttons (`<button>`) inside list/tree views STILL use `invisible` to hide individual row buttons. Applying `column_invisible` to buttons will not work.
- **Do NOT apply in Form/Search Views:** Only replace the attribute for `<field>` elements inside a `<tree>` or `<list>` context.

## Verification

Open the list/tree view in Odoo 17 or 18 dev mode, inspect the columns, and ensure columns marked as `column_invisible` are completely hidden from the table headers and body, without leaving blank slots. For top-level views, ensure no OwlErrors occur in `onWillRender` / `evalColumnInvisible`.
