# Per-user menu hiding via a record rule leaks on Odoo 19 (group-keyed `_visible_menu_ids` cache)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 19 (cache key changed vs 17/18)            |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `views`, `ir.ui.menu`, `ormcache`, `record-rule`, `menu`, `visibility`, `per-user`, `cache-leak`, `third-party`

---

## Problem

A module hides menu items **per user** (e.g. SerpentCS `scs_hide_menu_user_wise`):
it adds `res.users.hide_menu_ids` ↔ `ir.ui.menu.restrict_user_ids`, and a global
record rule on `ir.ui.menu`:

```xml
<field name="domain_force">[('restrict_user_ids', 'not in', user.ids)]</field>
```

On Odoo 19 the hiding **leaks across users who share the same groups**: user A
hides "Sales" for himself and user B (same groups) also loses it, or A keeps it —
whoever loads the menu first wins. Per-user hiding is effectively random.

## Root Cause

Odoo 19's menu-visibility helper is cached by the **group set**, not the user:

```python
# odoo/addons/base/models/ir_ui_menu.py
@tools.ormcache('frozenset(self.env.user._get_group_ids())', 'debug')
def _visible_menu_ids(self, debug=False):
    menus = self.with_context({}).search_fetch([...], [...]).sudo()   # rule applies to THIS search
    ...
```

The vendor record rule filters the `search_fetch` **inside** this method — but the
result is memoised under a key that is only the user's `frozenset(group_ids)`.
So the first same-group user to populate the cache freezes *their* restricted set
for every other same-group user. `load_menus`/`load_menus_root` sit on top and are
cached per `uid`, but they call `_filter_visible_menus → _visible_menu_ids`, so the
per-uid layer just re-serves the already-polluted group-cached set.

(On 17/18 the effective key/flow differed and the same rule appeared to work — this
is an Odoo 19 regression trap for per-user menu modules.)

## Solution ✅

Don't drive per-user hiding from a record rule that runs inside the group-cached
method. Deactivate it and subtract per-user in `_filter_visible_menus`, which is
**not** cached and always runs with the real user (its result is cached per uid):

```python
# overlay module (depends on the vendor one) — never edit the vendor files
class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()          # clean group-visible superset
        uid = self.env.uid
        if uid == SUPERUSER_ID or not menus:
            return menus
        restricted = menus.sudo().filtered(lambda m: uid in m.restrict_user_ids.ids)
        if not restricted:
            return menus
        hidden = self.sudo().search([('id', 'child_of', restricted.ids)])  # drop orphans too
        return menus - hidden
```

```xml
<!-- data/: deactivate the leaky rule so _visible_menu_ids returns the true superset -->
<record id="scs_hide_menu_user_wise.ir_ui_menu_rule_user" model="ir.rule">
    <field name="active" eval="False"/>
</record>
```

Because the group cache now returns the full group-visible superset (identical for
same-group users) and the subtraction happens in the per-uid, non-cached layer, the
result is exact and never leaks.

## ⚠️ Pitfalls

- **A record rule inside an `@ormcache` keyed more coarsely than the rule's own
  granularity always leaks.** The rule discriminates per user; the cache key is per
  group → mismatch. Check the cache key of any core method a rule feeds into.
- **`load_menus` being cached per `uid` is a red herring** — it delegates to the
  group-cached `_visible_menu_ids`, so the uid layer can't rescue you.
- **Fix in an overlay module, not the vendor files** — an App Store update wipes
  in-place edits; `auto_install: True` on the overlay keeps the fix attached.
- **Menu hiding is cosmetic**, never a security boundary — the model/action is still
  reachable by URL/action. Use real groups/ACLs for access control.
- **Also hide descendants** (`child_of`) of a hidden parent, or orphaned children
  linger in the tree.

## Verification (rolled back)

`solargy_hide_menu_fix/tests/test_menu_hiding.py`: two users **in the same group**;
hide a menu for A via `hide_menu_ids`; assert the menu is gone for A and **still
present for B** (`test_hidden_for_a_not_leaked_to_b`), plus the vendor rule is
deactivated. Fresh-DB `-i solargy_hide_menu_fix --test-enable`: 4/4 pass.

## Related

- `orm/odoo-19-res-users-groups-id-renamed-group-ids.md` (same-version res.users API shift)
- `orm/stored-compute-incomplete-depends-silent-staleness.md` (another "cache/depends granularity" trap)
