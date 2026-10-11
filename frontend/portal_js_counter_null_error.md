---
title: "Portal JS TypeError: Cannot set properties of null (setting 'textContent')"
category: "Frontend / Portal"
version: "16.0+"
last_verified: "2026-07-06"
---

# 📝 Problem
When creating a custom portal entry and implementing the `_prepare_home_portal_values(self, counters)` method in the portal controller, you might encounter a javascript crash in the Odoo frontend (`web.assets_frontend_lazy.min.js`):

```javascript
TypeError: Cannot set properties of null (setting 'textContent')
    at web.assets_frontend_lazy.min.js:8047:728
    at Array.forEach (<anonymous>)
    at ...
```

This error breaks the page interaction and leaves a "circle loop" (loading spinner) running indefinitely on the portal home page.

# 🕵️ Root Cause
This happens when you unconditionally return a counter in the `_prepare_home_portal_values` dictionary, even if the frontend didn't request it.

The Odoo Javascript calls the `/my/counters` RPC endpoint with a list of requested counters (e.g. `counters = ['project_count']`). If your controller adds another counter (e.g. `employee_count`) unconditionally, the RPC will return both.

The Javascript then loops over ALL keys in the response and tries to find the DOM element `[data-placeholder_count='employee_count']`. Since the frontend didn't request it, the element might not be rendered on the current view (or it was hidden by `force_show`), causing `querySelector` to return `null`. When it tries to set `el.textContent`, it crashes.

# ✅ Solution
**Always** check if the counter is in the `counters` list before computing or returning it in your controller.

**Bad Approach:**
```python
def _prepare_home_portal_values(self, counters):
    values = super()._prepare_home_portal_values(counters)
    # Unconditional logic
    values['employee_count'] = request.env['hr.employee'].search_count([])
    return values
```

**Good Approach:**
```python
def _prepare_home_portal_values(self, counters):
    values = super()._prepare_home_portal_values(counters)
    
    # Check if the counter was actually requested!
    if 'employee_count' in counters:
        values['employee_count'] = request.env['hr.employee'].search_count([])
        
    return values
```

# ⚠️ Pitfalls
- **Cache Persistence:** If you load the portal once with the bad code, the session might cache the counter presence. Even if you fix the code, the UI might still break until you clear your cookies or sign out and sign back in, because `force_show` might evaluate to `True` based on the old cached session data. Always test with a fresh incognito window if it still breaks after applying the fix.
