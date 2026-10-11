# Cross-Model Record Rules for Partner Classification Restrictions & Commercial Hierarchy Traversal

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | security                                   |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `security`, `ir.rule`, `res.partner`, `sale.order`, `account.move`, `commercial_partner_id`, `child_of`, `record-rules`

---

## Problem

When restricting users to specific customer classification levels, sales divisions, or partner categories (e.g. `allowed_customer_level_ids`), developers often write a single `ir.rule` on `res.partner`.
However:
1. Restricted users opening Sales Orders, Invoices, Delivery Orders, or Customer Visits still see **ALL records across the company** (e.g., viewing 1,347 orders instead of 647 allowed orders).
2. A permissive leaf like `('customer_level_id', '=', False)` in the partner rule leaks all unclassified customers to restricted users.
3. Checking only `customer_level_id` breaks contact/branch selection because subsidiary locations and delivery contacts frequently have `customer_level_id = False` while their parent company (`commercial_partner_id`) holds the level.
4. Portal controllers querying customers with `.sudo().search([('valid_customer', '=', True)])` leak all customers in portal dropdowns.

## Root Cause

- In Odoo, list and form views of transactional models (`sale.order`, `account.move`, `sale.visit`) execute SQL queries directly against their own tables. Record rules defined solely on `res.partner` do NOT filter searches on transactional models.
- Without explicit rules on transactional models, users can view, filter, and report on sales and invoices of unauthorized divisions.
- A naïve `res.partner` rule that checks `('customer_level_id', '=', False)` fails to differentiate between unclassified customers and non-customers (vendors, employees, partners).
- Addresses and branches under a parent company inherit their business classification from `commercial_partner_id`. Without traversing `commercial_partner_id.customer_level_id`, branch orders either get hidden or unlinked.

## Solution ✅

1. **Deploy Cascading Global Record Rules Across All Related Models:**
Define global record rules (`global="True"`) that evaluate to `[(1, '=', 1)]` when the user has no restrictions (fail-open), but strictly filter by allowed levels when restricted:

```xml
<!-- 1. res.partner: exempt non-customers, strictly filter customers and commercial parent -->
<record id="rule_partner_allowed_customer_levels" model="ir.rule">
    <field name="name">Partner: restricted to user's allowed customer levels</field>
    <field name="model_id" ref="base.model_res_partner"/>
    <field name="global" eval="True"/>
    <field name="domain_force">['|', '&amp;', ('valid_customer', '=', False), ('customer_rank', '=', 0), '|', ('customer_level_id', 'child_of', user.allowed_customer_level_ids.ids), ('commercial_partner_id.customer_level_id', 'child_of', user.allowed_customer_level_ids.ids)] if user.allowed_customer_level_ids else [(1, '=', 1)]</field>
</record>

<!-- 2. sale.order: filter by customer or commercial parent level -->
<record id="rule_sale_order_allowed_customer_levels" model="ir.rule">
    <field name="name">Sale Order: restricted to user's allowed customer levels</field>
    <field name="model_id" ref="sale.model_sale_order"/>
    <field name="global" eval="True"/>
    <field name="domain_force">['|', ('partner_id.customer_level_id', 'child_of', user.allowed_customer_level_ids.ids), ('partner_id.commercial_partner_id.customer_level_id', 'child_of', user.allowed_customer_level_ids.ids)] if user.allowed_customer_level_ids else [(1, '=', 1)]</field>
</record>

<!-- 3. account.move: filter customer invoices/refunds only; exempt vendor bills and entries -->
<record id="rule_account_move_allowed_customer_levels" model="ir.rule">
    <field name="name">Account Move: restricted customer invoices to allowed customer levels</field>
    <field name="model_id" ref="account.model_account_move"/>
    <field name="global" eval="True"/>
    <field name="domain_force">['|', ('move_type', 'not in', ('out_invoice', 'out_refund')), '|', ('partner_id.customer_level_id', 'child_of', user.allowed_customer_level_ids.ids), ('partner_id.commercial_partner_id.customer_level_id', 'child_of', user.allowed_customer_level_ids.ids)] if user.allowed_customer_level_ids else [(1, '=', 1)]</field>
</record>
```

2. **Add Model-Level `@api.constrains('partner_id')` Guardrails:**
Prevent restricted users from bypassing UI filters via API, import, or direct ID entry:

```python
@api.constrains('partner_id')
def _check_allowed_customer_level(self):
    if self.env.su:
        return
    user = self.env.user
    if not user.allowed_customer_level_ids or user._is_system() or user._is_admin():
        return
    allowed_ids = set(self.env['customer.level'].search([('id', 'child_of', user.allowed_customer_level_ids.ids)]).ids)
    for rec in self:
        partner = rec.partner_id
        if not partner:
            continue
        level = partner.customer_level_id or partner.commercial_partner_id.customer_level_id
        if not level or level.id not in allowed_ids:
            raise ValidationError(_("You cannot select customer '%s' because their level is outside your allowed customer levels.", partner.display_name))
```

3. **Scope Portal Controllers:**
When portal endpoints query customers using `sudo()`, always intersect with `user.allowed_customer_level_ids` if present.

## ⚠️ Pitfalls

- **Do NOT block vendor bills:** On `account.move`, always add `('move_type', 'not in', ('out_invoice', 'out_refund'))`. Otherwise, restricted users will receive `AccessError` when opening purchase bills or journal entries.
- **Do NOT block non-customers:** In `res.partner`, always exempt partners with `('valid_customer', '=', False), ('customer_rank', '=', 0)`.
- **Traverse `commercial_partner_id`:** Companies set classifications at HQ level; branch locations and shipping contacts must inherit visibility via `commercial_partner_id.customer_level_id`.
- **Manifest dependencies:** Referencing `sale.model_sale_order` or `account.model_account_move` in `ir.rule` XML requires adding `'sale_management'` and `'account'` to `depends` in `__manifest__.py`.

## Verification

Run simulation in Odoo shell:
```python
user = env['res.users'].search([('allowed_customer_level_ids', '!=', False)], limit=1)
orders = env['sale.order'].with_user(user).search([])
# Assert all orders strictly belong to user's allowed customer levels
for o in orders:
    lvl = o.partner_id.customer_level_id or o.partner_id.commercial_partner_id.customer_level_id
    assert lvl and lvl.id in allowed_subtree_ids
```

## References

- Related KB: [security/per-user-rule-fields-need-registry-cache-invalidation.md](per-user-rule-fields-need-registry-cache-invalidation.md)
- Fixed module: `custom/customer_level_chart`
