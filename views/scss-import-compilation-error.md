# CSS `@import` Breaks Odoo SCSS Asset Compilation

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                 |
| Last Verified | 2026-06-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `css`, `scss`, `import`, `assets`, `compilation`, `portal`, `fonts`

---

## Problem

> Adding a CSS `@import` statement (e.g., to load an external font like Google Fonts) inside an Odoo CSS or SCSS asset file causes the asset bundle compilation to fail or break entirely.
> This often results in a broken UI or a prominent red "A" error box indicating an SCSS compilation failure.

```css
/* Example of problematic code */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
```

## Root Cause

> Odoo's internal asset compiler (which processes SCSS/CSS into asset bundles) often chokes or behaves unpredictably when encountering external `@import` statements inside the CSS files themselves, as it attempts to resolve local file paths or handle the external URL during the bundle generation.

## Solution ✅

> **Never use `@import` inside CSS/SCSS files to load external resources.**
> 
> Instead, load external resources (like fonts) directly within the `<head>` of your XML template, or download the fonts and serve them locally.

**Step-by-step fix:**

1. Remove the `@import` statement from your `.css` or `.scss` file.
2. If you need the font, include it via a `<link>` tag in the relevant QWeb template (e.g., `web.layout` or `portal.frontend_layout`).

```xml
<xpath expr="//head" position="inside">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&amp;display=swap" rel="stylesheet"/>
</xpath>
```

3. Update the module (`-u module_name`) so Odoo recompiles the assets.

## ⚠️ Pitfalls

- Using `@import` might seem to work locally in some browser cached states but will fail completely when the asset bundle is regenerated.
- Hardcoding fonts without checking for RTL/LTR font compatibility can cause misalignment.

## Verification

> Hard refresh the browser (`Ctrl + F5` / `Cmd + Shift + R`). The UI should render correctly without the red SCSS compilation error box.
