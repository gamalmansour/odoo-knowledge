# Purchase Personal-Order Record Rule vs `partner.buyer_id` Hijack & Double-Validation Approval Bypass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-21                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `purchase`, `ir.rule`, `buyer_id`, `double_validation`, `ormcache`, `AccessError`, `purchase.team`

---

## Problem

When an Odoo deployment adds a "Personal Order" record rule on `purchase.order` for `purchase.group_purchase_user` (`['|', ('user_id', '=', user.id), ('user_id', '=', False)]`), two severe failures happen in production:

1. **Instant `AccessError` When Picking Vendors With a Default Buyer:** In Odoo core (`addons/purchase/models/purchase_order.py:455`), `onchange_partner_id()` (note: **no leading underscore**) silently sets `self.user_id = self.partner_id.buyer_id` whenever the selected vendor has a default `Buyer` assigned. If Buyer A picks a vendor whose `buyer_id` is Buyer B, saving the PO immediately triggers `AccessError` under the Personal Order rule.
2. **Double-Validation Finance Approval Bypass:** Admins frequently work around the `AccessError` (or grant a team lead visibility over junior buyers) by adding the user to `purchase.group_purchase_manager` (Administrator). However, `purchase.order._approval_allowed()` unconditionally returns `True` for `purchase.group_purchase_manager`, letting that buyer self-confirm multi-million POs without Finance approval!
3. **Stale `ir.rule` `ormcache` on Team Edits:** `ir.rule._compute_domain()` is `@tools.ormcache`-decorated. Dynamic team membership changes on a custom `purchase.team` model will NOT take effect in live `ir.rule` evaluations until `self.env.flush_all()` and `self.env.registry.clear_cache()` are called.

## Root Cause

- `purchase.order.onchange_partner_id()` unconditionally overwrites `user_id` with `partner.buyer_id`.
- `purchase.group_purchase_manager` bundles both "All Orders visibility" AND "Finance double-validation approval authority".
- `purchase.order.line` has NO direct `user_id` field (must traverse `order_id.user_id` in `ir.rule`).

## Solution ✅

1. **Create an intermediate privilege group (`sequence=15`)** under `purchase.res_groups_privilege_purchase` (Odoo 19 uses `privilege_id`, not `category_id`) that implies `purchase.group_purchase_user` and is implied by `purchase.group_purchase_manager` — giving supervisors team visibility WITHOUT Finance approval bypass.
2. **Guard `onchange_partner_id()` (exact name, no leading underscore!), `create()`, and `write()`** on `purchase.order`:
   ```python
   @api.onchange('partner_id', 'company_id')
   def onchange_partner_id(self):
       prev_user = self.user_id
       res = super().onchange_partner_id()
       if self._solargy_is_restricted_buyer() and self.user_id:
           visible_ids = self.env.user._get_solargy_visible_purchase_user_ids()
           if self.user_id.id not in visible_ids:
               self.user_id = prev_user if (prev_user and prev_user.id in visible_ids) else self.env.user
       return res
   ```
3. **Invalidate `ir.rule` `ormcache`** in `purchase.team` (`create`/`write`/`unlink`) and `res.users.write()` (when `'purchase_team_ids' in vals`) via `self.env.flush_all()` + `self.env.registry.clear_cache()`.
4. **Mirror 3-tier `ir.rule`s across `purchase.order`, `purchase.order.line` (via `order_id.*`), and `purchase.report`** (matching both `purchase_team_id` and `user_id in subordinate members` so historical POs with empty `purchase_team_id` are immediately visible).
5. **Deactivate legacy manual UI rules via an idempotent `<data noupdate="1">` `ir.actions.server`**, never inside upgrade hooks.

## ⚠️ Pitfalls

- **Method name trap:** In Odoo 19 `purchase.order`, the onchange method is `onchange_partner_id`, NOT `_onchange_partner_id`.
- **`@api.depends` trap:** `_compute_purchase_team_id` on `purchase.order` should depend ONLY on `('user_id', 'company_id')`, NOT `user_id.purchase_team_ids`, to avoid mass historical PO recompute/lock storms on roster edits.
- **Line-model field trap:** `purchase.order.line` uses `order_id.user_id` / `order_id.purchase_team_id` (never direct `user_id`), and `product_uom_id` (not `product_uom`) in Odoo 19.
- **Multi-company `_approval_allowed()` testing:** Core converts `company_id.po_double_validation_amount` via `self.env.company.currency_id`, so tests for secondary companies must use `.with_company(company_b)`.

## Verification

```bash
./odoo-bin -c solargy.conf -d solargy -i solargy_purchase_teams --test-enable --test-tags /solargy_purchase_teams --stop-after-init
```

## References

- Related module: `solargy_purchase_teams`
- Odoo 19 core: `addons/purchase/models/purchase_order.py` (`onchange_partner_id`, `_approval_allowed`, `button_approve`), `addons/purchase/security/purchase_security.xml`, `odoo/addons/base/models/ir_rule.py`
