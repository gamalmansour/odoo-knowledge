# Portal Dynamic UI for Mixed Data Models

**Category:** Views
**Severity:** 🟢 Low
**Versions:** 17, 18, 19
**Tags:** `qweb`, `portal`, `ui`, `dynamic`, `caching`, `mixed-targets`

## 📝 Problem Statement
When a single Odoo model (e.g. `sale.target`) is used to represent multiple distinct types of records (e.g., Revenue Targets vs Visit Targets), the portal view needs to dynamically adapt its layout to avoid confusing the user with irrelevant empty sections (e.g., showing €0.00 revenue for a user who only has a visit target).

Furthermore, after modifying the `portal_templates.xml` to add `t-if` conditions, users might complain that the changes are not visible in the browser, even after a module upgrade.

## ✅ Solution

### 1. Dynamic Layout via `t-if`
Instead of creating multiple portal templates or separate models, inject `t-if` conditions based on the core metric value:

```xml
<t t-if="target.target_amount > 0">
    <!-- Show Revenue stat boxes, revenue progress bar, and related tables -->
    <div class="revenue-section">...</div>
</t>

<t t-if="target.target_visit_count > 0">
    <!-- Show Visit stat boxes, visit progress bar, and related tables -->
    <div class="visit-section">...</div>
</t>
```
If a user has both metrics assigned, the portal gracefully stacks both sections. If they only have one, the irrelevant section is entirely hidden.

### 2. Bypassing QWeb Portal Caching
Odoo portal QWeb templates are aggressively cached in the browser. 
- **Action:** Instruct the user to perform a hard refresh (`Ctrl + F5`) or clear the browser cache.
- **Developer Note:** If the field referenced in the `t-if` condition (e.g., `target_visit_count`) was recently added to the Python model, you **MUST** restart the Odoo server and upgrade the module from the backend (`Apps -> Upgrade`). Without the module upgrade, the QWeb rendering engine will evaluate the new field as `None` or `False`, causing the `t-if` condition to fail silently.

## ⚠️ Pitfalls
- **Division by Zero:** Always ensure calculations like `achievement_pct` check if the target > 0 before dividing inside the Python compute method, not in QWeb.
- **Silent Failures:** If an XML field does not exist in the Python model due to a pending upgrade, QWeb simply suppresses the block instead of crashing, which can make debugging layout issues difficult.

---
*Last Verified: 2026-06-08*
