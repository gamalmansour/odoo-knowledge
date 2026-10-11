---
category: Frontend & UI
tags:
  - owl
  - action
  - layout
  - frontend
---

# OWL Action Component Hidden Under Navbar (Odoo 17+)

## Problem
When creating a custom client action component in OWL (Odoo 17+), the component renders, but the screen appears completely blank or missing. Elements are actually rendered but are hidden underneath the Odoo top navbar because they start at `top: 0` in the DOM.

## Solution ✅
You must wrap your top-level XML template in the `<Layout>` component from `@web/search/layout`.

1. Import `Layout` in your JS:
```javascript
import { Layout } from "@web/search/layout";
```

2. Add it to your component's components:
```javascript
static components = { Layout, ... };
```

3. Wrap your XML content:
```xml
<t t-name="your_module.YourComponent">
    <Layout display="{ controlPanel: {} }">
        <div class="your_content_wrapper">
            <!-- Your UI here -->
        </div>
    </Layout>
</t>
```

## ⚠️ Pitfalls
- Just adding CSS `margin-top: 50px` is hacky and breaks responsive views or changes to the Odoo UI. Always use `Layout`.
- Passing event functions directly via `t-on-click` requires proper scoping or using `.bind` (e.g. `onNodeClick.bind="onNodeClick"`) to avoid context loss in deep components.

## Odoo Versions
Tested on Odoo 17.0, 18.0, 19.0.

Last Verified: 2026-07-01
