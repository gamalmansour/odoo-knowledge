# 📝 OWL Client Action Scrolling Issue

**Category**: Frontend / OWL  
**Odoo Versions**: 16.0, 17.0, 18.0  
**Tags**: `#owl`, `#client-action`, `#dashboard`, `#css`, `#scrolling`, `#o_content`  
**Last Verified**: 2026-06-15  
**Author**: Gamal Mansour

---

## 🛑 Problem Statement
When building a custom dashboard or full-page UI using OWL Client Actions in Odoo, the vertical scrollbar may not appear, causing content that exceeds the screen height to be cut off (clipped) and unreachable.

Applying standard CSS like `overflow-y: auto;` or `height: 100%;` to the root `<div>` of your OWL template usually fails because the parent containers injected by Odoo's Action Manager (`.o_action_manager`) use Flexbox properties that suppress nested overflows unless properly structured.

## 💡 Solution / Best Practice
To enable native, smooth scrolling within an OWL Client Action, you MUST mimic Odoo's native view structure by wrapping your content in two specific CSS classes provided by the Odoo web framework: `.o_action` and `.o_content`.

### ✅ Do This (Correct Structure)
Wrap your entire component inside an outer `o_action` div, and an inner `o_content` div.

```xml
<t t-name="my_module.MyDashboard" owl="1">
    <div class="o_action">
        <div class="o_content">
            <!-- Your dashboard content goes here -->
            <div class="my_custom_wrapper">
                <h1>Hello World</h1>
                ... long content ...
            </div>
        </div>
    </div>
</t>
```

### ❌ Don't Do This (Common Mistake)
Do not place `o_action` and `o_content` on the same div, and do not attempt to force scrolling purely with absolute positioning without the `o_content` class.

```xml
<!-- This will FAIL to scroll properly in many cases -->
<t t-name="my_module.MyDashboard" owl="1">
    <div class="my_custom_wrapper o_action o_content" style="height: 100%; overflow: auto;">
        ... long content ...
    </div>
</t>
```

## ⚠️ Pitfalls & Gotchas
- **Nested Flexboxes**: If your custom wrapper inside `o_content` uses `display: flex; height: 100%;`, you might accidentally suppress the scroll again. Ensure your inner content allows its height to grow dynamically based on its children.
- **Header Elements**: If you want a fixed header that doesn't scroll with the content (like standard Odoo list views), you can add `<div class="o_control_panel">...</div>` *inside* `o_action` but *before* `o_content`.

## 🔗 Related References
- Odoo 17 Web Framework core CSS layout.
- [OWL Framework Documentation](https://github.com/odoo/owl)
