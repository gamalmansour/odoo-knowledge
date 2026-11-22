# Odoo 19 Field-Level Cost Hiding (`groups=`), `seller_ids` Context Trap, `_parent_store`, and Per-User Menu Hiding

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hide_cost`, `standard_price`, `groups`, `seller_ids`, `parent_store`, `hide_menu`, `res.users`, `odoo19`

---

## Problem

Three security & operational traps in custom Odoo 19 access-control modules:

1. **View-Only Cost Hiding Leaks via Export & RPC + `seller_ids` Context Crash:** Adding `groups="hide_cost.group_show_cost"` only in XML views leaves `standard_price`, `purchase_price`, `margin`, `avg_cost`, `total_value`, and `value` fully readable via Export, Pivot/Graph, and RPC. However, adding `groups=` on `product.template.standard_price` in Python triggers an `Access Rights Inconsistency` because `purchase.view_product_supplier_inherit` and `purchase.view_product_product_supplier_inherit` reference `standard_price` inside `<field name="seller_ids" context="{'default_price': standard_price, ...}"/>` for `purchase.group_purchase_user`.
2. **Privilege Escalation on Hierarchical Security Models:** Granting `base.group_user` `1,1,1,1` ACL on a hierarchy model (`customer.level`) used by `child_of` `ir.rule`s lets any restricted user reparent a forbidden node under their own allowed level and bypass all record rules. Missing `_parent_store = True` also degrades every `child_of` `ir.rule` across core models.
3. **Per-User Menu Hiding Breaking `res.users.write()` for Non-Admins:** Overriding `res.users.write()` to unconditionally write to `ir.ui.menu` (`restrict_user_ids`) causes `AccessError` whenever a non-admin user with hidden menus saves their own preferences (language, timezone, signature) and flushes the registry cache on every user save.

## Root Cause

- XML-only `groups=` hides fields in specific views only; ORM `fields.Float(groups=...)` enforces access across `fields_get`, `read`, `search_read`, Export, Pivot, Graph, and RPC.
- Core `purchase` product views evaluate `standard_price` in `seller_ids` `context` for `purchase.group_purchase_user`.
- `res.users.write()` runs as the current user when updating Preferences, and non-admins lack write access on `ir.ui.menu`.

## Solution ✅

### 1. ORM-Level `groups=` + `compute_sudo=True` + Strip `standard_price` from `purchase` `seller_ids` Context
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    standard_price = fields.Float(groups='hide_cost.group_show_cost', compute_sudo=True)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    # precompute=False + compute_sudo=True is MANDATORY: without precompute=False,
    # Odoo 19's _add_precomputed_values() reads margin/purchase_price in su=False
    # during sale.order.create() and raises AccessError for non-cost salespersons!
    purchase_price = fields.Float(groups='hide_cost.group_show_cost', compute_sudo=True, precompute=False)
    margin = fields.Float(groups='hide_cost.group_show_cost', compute_sudo=True, precompute=False)
    margin_percent = fields.Float(groups='hide_cost.group_show_cost', compute_sudo=True, precompute=False)
```
And in XML (with `'purchase'` in `depends`), remove `'default_price': standard_price` from `seller_ids` and `variant_seller_ids` `context` on `purchase.view_product_supplier_inherit` and `purchase.view_product_product_supplier_inherit`.

### 2. Lock Hierarchy ACL & Enable `_parent_store = True`
- Restrict `base.group_user` to `1,0,0,0` on `customer.level`, grant `1,1,1,1` only to `sales_team.group_sale_manager` / `base.group_system`.
- Add `_parent_store = True` + `parent_path = fields.Char(index=True)` on `customer.level` and `index=True` on `res.partner.customer_level_id`.

### 3. Guard `res.users.write()` and Protect `base.user_admin` (UID 2)
```python
def write(self, vals):
    res = super().write(vals)
    if "hide_menu_ids" not in vals:
        return res
    # sync restrict_user_ids only when hide_menu_ids actually changed
```
And in `ir.ui.menu._filter_visible_menus()`, exempt both `SUPERUSER_ID` (UID 1) and `base.user_admin` (UID 2) from menu hiding.

## ⚠️ Pitfalls

- **`product.value` in Odoo 19 is `models.Model`, NOT `models.TransientModel`** — inheriting it as `TransientModel` raises `TypeError` on registry load.
- **Never hide `res.partner.parent_id` unconditionally for non-branch partners** — restrict `branch_type` visibility to `is_company` only (`invisible="is_company and branch_type != 'branch'"`) so individual contacts (`is_company = False`) can still link to their parent company.

## Verification

- Playwright E2E + RPC with non-cost Salesperson & Warehouse User verifying: `fields_get` & direct RPC block cost/margin fields, Salesperson still creates & confirms Sale Orders cleanly, Warehouse User opens Inventory → Stock with 0 console errors & no `avg_cost`/`total_value`, non-admin with hidden menu saves own signature without `AccessError`, and `base.group_user` gets `AccessError` trying to edit `customer.level`.

## References

- Related file: `security/portal-savepoint-hidden-form-and-upload-hardening.md`
