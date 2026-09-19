# Deprecated kanban_image Helper in Odoo 17/18 OWL Kanban Views (TypeError: ctx.kanban_image is not a function)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `kanban`, `owl`, `kanban_image`, `qweb`, `views`, `deprecation`, `TypeError`, `image`

---

## Problem

When opening a Kanban view in Odoo 17 or 18 that contains image rendering code from older Odoo versions (Odoo 16 and below), the web client crashes with an OWL lifecycle error:

```
UncaughtPromiseError > OwlError
Uncaught Promise > An error occured in the owl lifecycle (see this Error's "cause" property)
OwlError: An error occured in the owl lifecycle (see this Error's "cause" property)
    Error: An error occured in the owl lifecycle (see this Error's "cause" property)
        at handleError (...)
        at App.handleError (...)
        at Fiber._render (...)
        at Fiber.render (...)
        at ComponentNode.initiateRender (...)

Caused by: TypeError: ctx.kanban_image is not a function
    at KanbanRecord.template (eval at compileTemplate ...)
```

## Root Cause

In Odoo 16 and earlier (Legacy Kanban / Widget architecture), the QWeb template compiler context exposed `kanban_image(model, field, id, cache, default)` as a built-in evaluation helper.

Starting in Odoo 17 and Odoo 18 with the migration of Kanban views to modern OWL components (`KanbanRecord` / OWL compiler), `kanban_image` was removed from `ctx` (the QWeb template evaluation scope). Attempting to call `kanban_image(...)` in `<t t-name="card">` or `<t t-name="kanban-box">` raises `TypeError: ctx.kanban_image is not a function`.

## Solution ✅

### 1. Modern Odoo 18 Flex Card Architecture (Recommended)

In Odoo 18, Kanban cards use `<t t-name="card" class="flex-row">` with semantic `<aside class="o_kanban_aside_full">` and `<main>` tags. Render images directly using the standard `<field widget="image"/>`:

```xml
<!-- BEFORE (Legacy - Crashes in Odoo 17/18) -->
<t t-name="card" class="o_kanban_record_has_image_fill">
    <main>
        <div class="o_kanban_image_fill_left d-none d-md-block" t-attf-style="background-image:url(#{kanban_image('construction.site.photo', 'image_512', record.id.raw_value)})"/>
        <img class="d-md-none w-100" t-att-src="kanban_image('construction.site.photo', 'image_512', record.id.raw_value)" alt="Photo"/>
        <div class="oe_kanban_details">
            <strong><field name="name"/></strong>
        </div>
    </main>
</t>

<!-- AFTER (Odoo 18 OWL Standard) -->
<kanban>
    <!-- Always declare the image field in kanban tag -->
    <field name="image_512"/>
    <templates>
        <t t-name="card" class="flex-row">
            <aside class="o_kanban_aside_full">
                <field name="image_512" widget="image" options="{'img_class': 'object-fit-cover w-100 h-100'}" alt="Photo"/>
            </aside>
            <main class="ps-2">
                <div class="oe_kanban_details">
                    <strong class="o_kanban_record_title"><field name="name"/></strong>
                </div>
            </main>
        </t>
    </templates>
</kanban>
```

### 2. Direct HTTP Image Route URL (Alternative when custom CSS div is required)

If you must use a standard `<img>` or `background-image` style attribute instead of the `<field>` image widget, reference the standard web image route URL `/web/image/<model>/<id>/<field>`:

```xml
<div class="o_kanban_image_fill_left d-none d-md-block"
     t-attf-style="background-image:url('/web/image/construction.site.photo/#{record.id.raw_value}/image_512')"/>
<img class="d-md-none w-100"
     t-attf-src="/web/image/construction.site.photo/#{record.id.raw_value}/image_512" alt="Photo"/>
```

## ⚠️ Pitfalls

- **Missing Field in `<kanban>`**: When using `<field name="image_512" widget="image"/>` or reading `record.image_512`, make sure `<field name="image_512"/>` is listed inside `<kanban>` so the ORM includes it in the `web_search_read` payload specification.
- **`raw_value` vs `value`**: In Odoo 17/18 OWL kanban, `record.id.raw_value` or `record.id.value` contains the integer ID. Using direct `<field widget="image"/>` avoids having to construct raw URLs manually and handles image caching automatically.
- **Class naming in cards**: Avoid legacy `o_kanban_record_has_image_fill` inside `<main>`. Use `<aside class="o_kanban_aside_full">` alongside `<main class="ps-2">` to get clean responsive flex layouts matching core Odoo 18 views (such as `res.partner` and `hr.employee`).

## Verification

1. Upgrade the module:
   ```bash
   odoo-bin -c odoo.conf -d database_name -u module_name --stop-after-init
   ```
2. Navigate to the Kanban view in the web client.
3. Verify that cards render with thumbnails and that no OWL lifecycle errors appear in the browser developer console.
