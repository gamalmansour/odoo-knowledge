# OWL `t-esc` Renders Literal "false" for Empty Odoo Fields, and Template Helpers Are Per-Component

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-11                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `qweb`, `t-esc`, `many2one`, `client-action`, `false`, `helper-scope`

---

## Problem

Two related traps when a custom OWL client action renders records fetched from Odoo:

**1. Empty fields show the word "false".** An empty Odoo char / many2one field comes back over RPC as Python `False` → JSON `false` → JS boolean `false`. A bare `<t t-esc="record.field"/>` then renders the literal string **`false`** on screen (tables full of "false", subtitles reading "false false", etc.).

**2. A display helper defined on some components is NOT available on others.** Wrapping the fix in a helper method (e.g. `m2o()`) that is defined on `PatientList` but calling it from the ROOT `ClinicDashboard` template throws at render:

```
Odoo Client Error — UncaughtPromiseError > OwlError
Caused by: TypeError: ctx.m2o is not a function
    at ClinicDashboard.template (eval at compile ...)
```

The user sees a blank **"Oops! Something went wrong"** dialog. Neither trap is caught by `odoo-bin -u <module>` or a static HTML preview — they only surface in a live, logged-in browser render.

## Root Cause

- OWL's `t-esc` stringifies a boolean `false` to `"false"` (it only treats `null`/`undefined` as empty, not `false`).
- OWL template expressions evaluate against **that component's instance** (`ctx`). A method is only in scope for the template of the class that defines it. Sibling components each need their own copy (or a shared mixin). Calling a missing one is a render-time `TypeError`, not a load/compile error.

## Solution ✅

Guard every binding that can be empty, and make sure the helper exists on the component that uses it.

```xml
<!-- scalar char/text field: guard with || '' -->
<t t-esc="appt.source || ''"/>
<t t-esc="p.name_ar || ''"/>

<!-- many2one [id, name] (or false): use a display helper, NOT raw [1] -->
<t t-esc="m2o(appt.physician_id)"/>
```

```javascript
// Define the SAME helper on EVERY component whose template calls it.
// (root ClinicDashboard AND each child that renders records)
m2o(v) { return Array.isArray(v) ? v[1] : (v || ""); }
```

Note `m2o()` above doubles as a universal display coercer: many2one array → name, any falsy → "".

## ⚠️ Pitfalls

- Don't use `field || ''` on a **many2one** — the value is a truthy `[id, name]` array, so `||` returns the array and OWL renders `"5,Dr X"`. Use the `m2o()` helper (or `field and field[1] or ''`) for m2o.
- The `X is not a function` crash is **per-component**: it fires only for the template that calls the missing helper. A screen using the helper on a component that HAS it can pass while a sibling screen crashes — test every screen.
- `-u module`, `node --check`, XML well-formedness, and static previews all pass while these bugs exist. **Only a logged-in browser render catches them.**
- Prod asset mode caches the compiled bundle; a plain reload can serve the STALE bundle and mask both the bug and your fix. Run the dev server with **`--dev=all`** so templates/JS are read fresh from disk, then a normal refresh shows edits. (Python model changes still need a full restart.)

## Verification

1. Start with `--dev=all`, log in, open the client action in the browser.
2. Confirm empty cells render blank (not "false") and no "Oops!" dialog.
3. Check the browser console is clean and inspect a specific cell:
```javascript
// in the page console — empty field should be "" not "false"
[...document.querySelectorAll('td')].some(td => td.textContent.trim() === 'false')  // => false
```

## References

- Related file: `frontend/owl-client-action-props-missing-odoo19.md`
- Related file: `frontend/owl-client-action-scrolling.md`
