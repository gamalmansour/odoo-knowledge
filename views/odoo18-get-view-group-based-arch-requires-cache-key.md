# Per-Group Arch Modification in `_get_view()` Requires Overriding `_get_view_cache_key()`

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-26                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `_get_view`, `_get_view_cache_key`, `ormcache`, `security`, `create`, `kanban`

---

## Problem

When overriding `Model._get_view()` to conditionally strip `create="0"`, `edit="0"`, or `delete="0"` on a specific view (such as a `res.partner` Developers Kanban) based on `self.env.user.has_group(...)`, the first user who loads the view poisons the view cache for every other user:

- If an Agent loads the view first, Listing Managers also lose the `New` button (`create="0"` stays cached).
- If a Listing Manager loads the view first, Agents still see the `New` button.

## Root Cause

In `odoo/addons/base/models/ir_ui_view.py`, `_get_view_cache()` wraps `_get_view()` with `@tools.ormcache('self._get_view_cache_key(view_id, view_type, **options)', cache='templates')`.

The default `_get_view_cache_key()` returns:

```python
(view_id, view_type, options.get('mobile'), self.env.lang) + tuple(
    (key, value) for key, value in self.env.context.items() if key.endswith('_view_ref')
)
```

It intentionally does **not** include `self.env.uid` or user groups (because normal XML `groups="..."` filtering runs *after* `_get_view_cache()` in `get_view()`). Any custom group-dependent arch mutation inside `_get_view()` is therefore shared across all users unless the cache key is partitioned.

## Solution ✅

Always override `_get_view_cache_key()` alongside `_get_view()` to append a minimal boolean partition key (e.g., only for the affected `view_type`), and always pair UI hiding with backend `create()` / `write()` `AccessError` guards:

```python
def _can_manage_developers(self) -> bool:
    return bool(
        self.env.su
        or self.env.user.has_group('my_module.group_listing_manager')
        or self.env.user.has_group('base.group_system')
    )

@api.model
def _get_view_cache_key(self, view_id=None, view_type='form', **options):
    key = super()._get_view_cache_key(view_id=view_id, view_type=view_type, **options)
    if view_type == 'kanban':
        return key + (self._can_manage_developers(),)
    return key

@api.model
def _get_view(self, view_id=None, view_type='form', **options):
    arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
    if view_type == 'kanban' and view and not self._can_manage_developers():
        target = self.env.ref('my_module.view_developers_kanban', raise_if_not_found=False)
        if target and view.id == target.id:
            arch.set('create', '0')
            arch.set('edit', '0')
            arch.set('delete', '0')
    return arch, view
```

## ⚠️ Pitfalls

- **Never** add `self.env.uid` to `_get_view_cache_key()` — that creates one template cache entry per user and causes memory bloat. Use a single boolean permission flag so only 2 cache entries exist.
- **Never** rely on `create="0"` in the view alone for security; always enforce the same permission check in `create()` / `write()` via `AccessError`.
- Compare `view.id == target.id` using `self.env.ref(..., raise_if_not_found=False)` rather than fragile string matching.

## Verification

In a `TransactionCase`, call `get_views([(target_view.id, 'kanban')])` first as a regular user (`assertIn('create="0"', arch)`) and immediately after as a manager (`assertNotIn('create="0"', arch)`), then repeat in reverse order.

## References

- Core cache key: `odoo/addons/base/models/ir_ui_view.py` (`_get_view_cache_key`, `_get_view_cache`)
