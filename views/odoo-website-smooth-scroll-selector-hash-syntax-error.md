# Website Smooth-Scroll querySelector '#' SyntaxError on Empty Anchor or OAuth Redirect

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19, All                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `website`, `javascript`, `querySelector`, `oauth`, `syntaxerror`, `smooth-scroll`

---

## Problem

When navigating to or returning from external redirects (such as Facebook / Meta OAuth redirect, which appends `#_=_` to the URL) or when clicking empty anchor links (`<a href="#">`), Odoo frontend crashes with an `UncaughtClientError`:

```text
UncaughtClientError > SyntaxError
Uncaught Javascript Error > Failed to execute 'querySelector' on 'Document': '#' is not a valid selector.
SyntaxError: Failed to execute 'querySelector' on 'Document': '#' is not a valid selector.
    at HTMLAnchorElement.<anonymous>
```

This prevents external integrations (like Odoo Social Marketing account linking) and frontend dropdowns/modals from working properly.

---

## Root Cause

A common client-side JavaScript smooth-scrolling pattern listens to all anchors matching `a[href^="#"]`:

```javascript
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});
```

If an element has `href="#"` or `href="#_=_"` (standard Meta/Facebook OAuth callback hash):
1. `this.getAttribute('href')` evaluates to `'#'` or `'#_=_'`.
2. `document.querySelector('#')` is executed. In CSS selectors, a hash without a valid identifier name is an illegal syntax.
3. The browser engine throws `SyntaxError: '#' is not a valid selector`.
4. Odoo's frontend error handler intercepts this and displays an intrusive modal dialog blocking user action.

---

## Solution ✅

Implement defensive selector verification and error shielding:

1. Guard against empty hashes, `'#'`, and OAuth hashes (`'#_=_'`).
2. Wrap `document.querySelector` in a `try...catch` block.
3. Only call `e.preventDefault()` if a valid target was resolved.

```javascript
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (!href || href === '#' || href === '#_=_') { 
            return; 
        }
        let target = null;
        try { 
            target = document.querySelector(href); 
        } catch (err) {
            // Silently ignore non-standard or invalid selector targets
        }
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});
```

In Odoo QWeb views (`ir.ui.view`), ensure characters are properly XML-escaped if needed, or avoid XML entities by using standard JS comparison syntax.

---

## ⚠️ Pitfalls

- **Calling `e.preventDefault()` unconditionally:** Doing this on `a[href^="#"]` breaks Bootstrap modals, accordions, and dropdown toggles that rely on default click event propagation.
- **Unescaped `&&` in QWeb views:** Writing `if (href && href.length > 1)` inside `<script>` in QWeb XML will fail XML parsing. Either use CDATA or simple condition checks like `if (!href || href === '#' || href === '#_=_') { return; }`.

---

## Verification

1. Inspect elements with `href="#"` or URLs containing `#_=_`.
2. Click the links or trigger the OAuth redirect.
3. Ensure no unhandled client exceptions appear in browser developer console or Odoo error dialogs.
