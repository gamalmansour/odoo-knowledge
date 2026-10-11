# Odoo 18 "View types not defined tree found in act_window"

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | upgrade                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `upgrade`, `odoo18`, `owl`, `act_window`, `views`, `tree`, `list`, `web-client`

---

## Problem

When clicking a button or stat button that executes an `ir.actions.act_window` method in Python, the OWL web client crashes with the following error modal:

```
UncaughtPromiseError

Uncaught Promise > View types not defined tree found in act_window action undefined

Error: View types not defined tree found in act_window action undefined
    at _executeActWindowAction (web.assets_web.min.js:10087:26)
    at doAction (web.assets_web.min.js:10113:8)
    at async Object.doActionButton (web.assets_web.min.js:10124:249)
```

## Root Cause

In **Odoo 18**, the core frontend completely deprecated and removed the `tree` view type name in favor of `list`.
While Odoo provides an XML compatibility layer for `<record ... view_mode="tree,form">` (auto-aliasing tree to list), **Python methods returning action dictionaries** that explicitly specify `views: [(view_id, tree), (False, form)]` are sent directly as JSON payloads to the frontend OWL Action Manager (`_executeActWindowAction`).

Because the OWL action manager looks up the registered view definitions and only has `list` registered, finding `tree` raises:
`Error: View types not defined tree found in act_window action undefined`.

## Solution ✅

Replace all occurrences of `tree` with `list` inside the `views` list of Python action dictionaries:

```python
# ❌ Before (Crashes in Odoo 18)
return {
    'name': _('VO Register'),
    'type': 'ir.actions.act_window',
    'res_model': 'contract.amendment',
    'view_mode': 'list,form',
    'views': [(tree_view_id, 'tree'), (False, 'form')],
    'domain': [('contract_id', '=', self.id)],
}

# ✅ After (Odoo 18 Compatible)
return {
    'name': _('VO Register'),
    'type': 'ir.actions.act_window',
    'res_model': 'contract.amendment',
    'view_mode': 'list,form',
    'views': [(tree_view_id, 'list'), (False, 'form')],
    'domain': [('contract_id', '=', self.id)],
}
```

## ⚠️ Pitfalls

- **Grepping for `view_mode` misses this:** Developers usually search for `view_mode` in XML/Python and change it to `list,form`, but overlook custom `views: [(id, tree)]` tuples in action helper methods.
- **Server reload required:** Since this is defined inside Python model methods, changes will NOT take effect until the Odoo server process reloads or restarts.

## Verification

Call the method in python or click the button in UI:

```python
action = record.action_view_vo_register()
assert action['views'][0][1] == 'list', "View type must be list!"
```
