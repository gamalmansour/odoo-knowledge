# HSE Subcontractor Penalties and IPC Billing Coupling

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | setup                                      |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `hse`, `subcontractor`, `penalty`, `ipc`, `deductions`, `financials`

---

## Problem

The Subcontractor Penalties (`hse.penalty`) menu view appears completely empty after deploying the HSE and Subcontracting modules, or applying penalties fails with configuration/domain errors:
1. Penalties cannot be selected or applied from HSE Actions (`CAPA`).
2. Target Subcontractor IPC list is empty in the penalty wizard (`hse.penalty.wizard`).
3. Reversing a penalty does not log an audit trail on the originating HSE CAPA record.
4. Penalties list view displays only invoice references without showing the subcontractor partner name.

## Root Cause

1. **Configuration Gate**: `construction_hse.enable_subcontractor_penalty` in `ir.config_parameter` defaults to `'False'`.
2. **IPC Workflow State Constraint**: `hse.penalty.wizard` uses a strict domain `[('contract_id', '=', subcontractor_id), ('state', '=', 'draft')]`. If existing subcontractor invoices are already `submitted`, `approved`, or `invoiced`, no target IPC is available to absorb the penalty deduction.
3. **Data Model Visibility**: `hse.penalty` originally stored `invoice_id` and `project_id`, but omitted a stored `subcontractor_id` (`related='invoice_id.partner_id'`), preventing direct list grouping and searching by subcontractor company.

## Solution ✅

### 1. Enable Subcontractor Penalty Parameter

In Odoo Settings (or data/shell):
```python
env['ir.config_parameter'].sudo().set_param('construction_hse.enable_subcontractor_penalty', 'True')
```

### 2. Add Subcontractor Partner & Agreement to `hse.penalty`

```python
class HsePenalty(models.Model):
    _name = 'hse.penalty'
    _inherit = ['mail.thread']

    subcontractor_id = fields.Many2one(
        'res.partner',
        related='invoice_id.partner_id',
        string='Subcontractor',
        store=True,
        readonly=True,
    )
    contract_id = fields.Many2one(
        'contract.subcontractor',
        related='invoice_id.contract_id',
        string='Subcontract Agreement',
        store=True,
        readonly=True,
    )
```

### 3. Add Reversible Audit Logging & Strict Positive Constraints

```python
    @api.constrains('amount')
    def _check_amount(self) -> None:
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Penalty amount must be strictly greater than zero."))

    def action_reverse(self) -> None:
        for rec in self:
            if rec.state != 'applied':
                raise UserError(_("Only applied penalties can be reversed."))
            if rec.invoice_id.state != 'draft':
                raise UserError(_("A penalty can only be reversed while its IPC is still in draft."))
            rec.state = 'reversed'
            rec.invoice_id.message_post(
                body=_("HSE penalty %(name)s of %(amount)s was reversed.") % {'name': rec.name, 'amount': rec.amount})
            if rec.action_id:
                rec.action_id.message_post(
                    body=_("HSE penalty %(name)s of %(amount)s on IPC %(invoice)s was reversed.") % {
                        'name': rec.name, 'amount': rec.amount, 'invoice': rec.invoice_id.name})
```

### 4. Update XML Views with Subcontractor Grouping

Add `subcontractor_id` to tree view, form view, and search view with `<filter string="Subcontractor" name="group_subcontractor" context="{'group_by': 'subcontractor_id'}"/>`.

## ⚠️ Pitfalls

- **Reversal Timing**: Never allow penalty reversal after the subcontractor IPC is approved or invoiced, otherwise vendor bills in accounting will diverge from safety records.
- **Compute Override `@api.depends`**: When inheriting `contract.subcontractor.invoice` to adjust `net_payable -= safety_deduction`, always repeat the entire parent `@api.depends` field list to avoid freezing stored financial computations.

## Verification

```bash
/Users/gamal/odoo/odoo18.0/.venv/bin/python /Users/gamal/odoo/odoo18.0/odoo-bin shell -c /Users/gamal/odoo/odoo18.0/odoo18_con.conf -d hadhoud_demo --no-http << 'EOF'
penalties = env['hse.penalty'].search([])
print("Penalties count:", len(penalties))
for p in penalties:
    print(p.name, p.subcontractor_id.name, p.amount, p.state, p.invoice_id.safety_deduction)
EOF
```
