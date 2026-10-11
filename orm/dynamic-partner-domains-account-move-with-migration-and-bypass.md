# Dynamic Partner Domains on Account Move with Migration Backfill and Settlement Bypass

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19 (All)                       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `account.move`, `partner_id`, `dynamic-domain`, `migration`, `backfill`, `commission`, `bypass`, `constrains`

---

## Problem

When business requirements demand separating valid customers from valid vendors using boolean flags on `res.partner` (e.g. `valid_customer`, `valid_vendor`), developers encounter three severe production traps:

1. **XML View Domain Limitation on `account.move`:**
   In `account.move` form views, writing a domain on `partner_id` such as `domain="['|', ('move_type', 'in', ('out_invoice', 'out_refund')), ('valid_customer', '=', True)]"` fails because `move_type` is a field on `account.move`, NOT on the target comodel `res.partner`. Filtering dynamically based on whether the document is a customer invoice or vendor bill cannot be written as a static domain leaf.

2. **Immediate Production Lockout (Zero-Day Migration Trap):**
   Adding `valid_customer = fields.Boolean(default=False)` with `@api.constrains('partner_id')` immediately blocks users from confirming orders, creating visits, or issuing invoices for all existing partners because existing rows have `valid_customer = False`.

3. **Silent Automation Crash on Commission Vendor Bills:**
   Restricting vendor bills (`in_invoice`) to `valid_vendor = True` causes automated expense or commission settlement workflows to crash. For example, `salesperson_commission` generates an `in_invoice` payable to `salesperson.partner_id` (an employee/user partner who is not flagged as a commercial vendor).

---

## Root Cause

1. The web client evaluates `domain="..."` on relational fields against the **target comodel** fields, unless dynamic field evaluation is provided via a computed Char domain field.
2. In relational databases, new boolean columns without a backfill script default to `False` or `NULL`, invalidating all historical master data against strict new validation constraints.
3. Internal company documents (commission payouts, expense reimbursements) often reuse `account.move` with `in_invoice` type, but their partners are internal employees/users rather than external vendors.

---

## Solution ✅

### 1. Dynamic Domain Char Field on `account.move`
Compute a dynamic domain string that adapts according to `move_type`:

```python
class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_id_domain = fields.Char(
        string='Partner Domain',
        compute='_compute_partner_id_domain',
        readonly=True,
    )

    @api.depends('move_type')
    def _compute_partner_id_domain(self):
        for move in self:
            if move.is_sale_document(include_receipts=True):
                move.partner_id_domain = "[('valid_customer', '=', True)]"
            elif move.is_purchase_document(include_receipts=True):
                move.partner_id_domain = "[('valid_vendor', '=', True)]"
            else:
                move.partner_id_domain = "[]"
```

In the inherited XML view:
```xml
<record id="view_move_form_valid_partner" model="ir.ui.view">
    <field name="name">account.move.form.valid.partner</field>
    <field name="model">account.move</field>
    <field name="inherit_id" ref="account.view_move_form"/>
    <field name="arch" type="xml">
        <field name="partner_id" position="attributes">
            <attribute name="domain">partner_id_domain</attribute>
        </field>
        <xpath expr="//field[@name='partner_id']" position="before">
            <field name="partner_id_domain" invisible="1"/>
        </xpath>
    </field>
</record>
```

### 2. Idempotent SQL Backfill in Model `init()`
Automatically validate existing active companies and vendors upon module upgrade so business is never halted:

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    valid_customer = fields.Boolean(
        string='Valid Customer',
        default=False,
        index=True,
    )
    valid_vendor = fields.Boolean(
        string='Valid Vendor',
        default=False,
        index=True,
    )

    def init(self):
        super().init()
        # Backfill existing customer companies
        self.env.cr.execute("""
            UPDATE res_partner
            SET valid_customer = TRUE
            WHERE valid_customer IS NOT TRUE
              AND active = TRUE
              AND is_company = TRUE
              AND (
                  customer_rank > 0
                  OR id IN (SELECT DISTINCT partner_id FROM sale_order)
                  OR id IN (SELECT DISTINCT partner_id FROM sale_visit)
              );
        """)
        # Backfill existing vendor companies
        self.env.cr.execute("""
            UPDATE res_partner
            SET valid_vendor = TRUE
            WHERE valid_vendor IS NOT TRUE
              AND active = TRUE
              AND (
                  supplier_rank > 0
                  OR id IN (SELECT DISTINCT partner_id FROM purchase_order)
              );
        """)
```

### 3. Exemption Guard for Commission / Internal Settlement Bills
When enforcing `@api.constrains`, provide a dedicated bypass check:

```python
    @api.constrains('partner_id', 'move_type')
    def _check_valid_account_move_partner(self):
        for move in self:
            if not move.partner_id:
                continue
            if move.is_sale_document(include_receipts=True):
                if not move.partner_id.valid_customer:
                    raise ValidationError(_("Customer Invoices and Credit Notes can only be issued to validated customers."))
            elif move.is_purchase_document(include_receipts=True):
                # Bypass internal commission settlements and explicit bypass context
                is_commission = (
                    (move.ref and 'Commission Settlement' in move.ref)
                    or move.env.context.get('skip_vendor_check')
                )
                if not is_commission and not move.partner_id.valid_vendor:
                    raise ValidationError(_("Vendor Bills can only be issued to validated vendors."))
```

---

## ⚠️ Pitfalls

- **Inheritance Missing in Manifest:** Inheriting `account.move` requires `'account'` explicitly in `'depends'` in `__manifest__.py`.
- **Portal Controllers Overhaul:** XML views do NOT constrain portal web forms (e.g. `/my/orders/new`). Always filter partner search (`[('valid_customer', '=', True)]`) and validate POST submissions inside portal controllers.
- **Unit Test Breakage:** Existing unit tests that mock partners via `cls.env['res.partner'].create({'name': 'X'})` will default `valid_customer` to `False` and fail downstream SO/Visit creation tests. Ensure test partners specify `'valid_customer': True`.

---

## Verification

```bash
# Run unit tests covering constraint validation and bypass
python3 odoo-bin -c custom.conf -u sale_visit --test-enable --test-tags=sale_visit --stop-after-init
```
