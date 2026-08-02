# Per-User Record-Rule Fields Silently Ignore Changes Until Restart — `ir.rule._compute_domain` Is ormcached

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-08-02                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `ir.rule`, `ormcache`, `clear_cache`, `_get_invalidation_fields`, `record-rules`, `per-user`, `restriction`

---

## Problem

A per-user visibility restriction implemented as a record rule reading a custom field, e.g.:

```python
domain_force = "[('categ_id', 'child_of', user.restricted_category_ids.ids)] if user.restricted_category_ids else [(1, '=', 1)]"
```

works in tests and right after `-i`, but on a live server **assigning or un-assigning a user does nothing** — the restriction only kicks in after a server restart or module upgrade. Worse: an UN-assignment lingers (user stays blocked).

## Root Cause

`ir.rule._compute_domain` is **`@ormcache`d per (uid, model, mode)** — the domain expression is EVALUATED once (reading the user's field at that moment) and the RESULT is cached in the registry. The cache is only cleared when:

- `res.users.write()` touches a field listed in `res.users._get_invalidation_fields()` — a fixed set (`group_ids`, `active`, `lang`, `tz`, `company_id[s]`, session fields). **Custom m2m fields are NOT in it.**
- Something else clears the registry cache (restart, `-u`, group changes...).

So a custom per-user field written on the USER never invalidates, and a field written on the OTHER side of the relation (e.g. `product.category.restricted_user_ids`) doesn't even pass through `res.users.write()`.

Why tests lie: in a test/`-i` run the first rule evaluation happens AFTER the assignment, so the cache is fresh and everything looks fine.

## Solution ✅

1. **Field written on the user side:** extend the invalidation set —

```python
@api.model
def _get_invalidation_fields(self):
    invalidation_fields = super()._get_invalidation_fields()
    invalidation_fields.add('allowed_picking_type_ids')
    return invalidation_fields
```

2. **Field written on the other side of the relation** (assignment lives on the category/level/etc. form): clear the registry cache in that model's create/write/unlink —

```python
def write(self, vals):
    res = super().write(vals)
    if 'restricted_user_ids' in vals:
        self.env.registry.clear_cache()
    return res
```

(plus the same guard in `create` when the field is passed, and in `unlink` when the records being deleted carry assignments).

3. **Regression test that primes the cache first** — search as the user BEFORE assigning, then assign, then assert the restriction applies. Without the prime step the test proves nothing.

## ⚠️ Pitfalls

- `registry.clear_cache()` is registry-wide — fine for admin-frequency assignment changes, don't put it on hot paths.
- `--dev` mode may disable the conditional ormcache, hiding the bug in dev and shipping it to production.
- The same trap applies to ANY cached consumer of per-user fields (e.g. `ir.ui.menu` visibility — see [per-user-menu-hiding-leaks-through-group-keyed-visible-menu-cache](../views/per-user-menu-hiding-leaks-through-group-keyed-visible-menu-cache.md)).
- Audit checklist for every per-user rule field: user-side write covered? other-side write covered? unlink covered?

## Verification

Reproduced live (Odoo 19, `product_category_restriction`): assignment on the category had no effect until restart. After adding `_get_invalidation_fields` + category-side `clear_cache()`, the prime-then-assign regression tests pass in all three restriction modules (15/15), and assignment/un-assignment apply immediately.

## References

- Core: `odoo/addons/base/models/ir_rule.py::_compute_domain` (ormcache), `odoo/addons/base/models/res_users.py::_get_invalidation_fields`
- Fixed modules: [product_category_restriction](file:///Users/gamal/odoo/odoo19.0/custom/product_category_restriction/), [stock_picking_type_restriction](file:///Users/gamal/odoo/odoo19.0/custom/stock_picking_type_restriction/), [customer_level_chart](file:///Users/gamal/odoo/odoo19.0/custom/customer_level_chart/)
- Related KB: [extending-portal-groups-to-internal-users-implied-unlink](extending-portal-groups-to-internal-users-implied-unlink.md)
