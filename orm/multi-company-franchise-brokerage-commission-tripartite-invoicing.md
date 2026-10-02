# Multi-Company Tripartite Brokerage Commission Invoicing & Deal Lifecycle

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `multi-company`, `commission`, `realestate`, `brokerage`, `invoicing`, `vendor-bill`, `account.move`, `cancellation`, `idempotency`, `odoo18`

---

## Problem

In multi-company real estate brokerage systems (Headquarters/Parent Company + Franchise branches), closing and contracting a deal requires balancing both customer receivables and inter-company obligations across legal entities.

Two critical pitfalls occur in practice:
1. **One-Sided Inter-Company Invoicing (Missing Tripartite Bill):**
   When a sub-franchise closes a developer deal, contracting the deal generates a customer invoice from Headquarters to the Developer, and a customer invoice from the Franchise to Headquarters. However, Headquarters fails to generate the corresponding **Vendor Bill (`in_invoice`)** acknowledging the payable liability to the franchise partner. This leaves Headquarters' accounts with unrecorded debt and broken inter-company reconciliation (`TC-021`).
2. **Missing Journal Crash in Fresh Franchises:**
   Freshly created franchise companies often lack default Sales (`sale`) or Purchase (`purchase`) journals. Contracting a franchise deal raises `UserError: No Sales journal found in company...` or crashes during inter-company document generation.
3. **Orphaned Financial Documents on Deal Cancellation:**
   When a client backs out or a deal falls through (`action_set_cancelled`), the system sets the state to `cancelled` but leaves generated draft invoices, vendor bills, and internal commission lines untouched. This pollutes general ledger reports and distorts commission cron jobs (`TC-042`).

---

## Root Cause

1. The invoice generation loop only created `out_invoice` documents, forgetting that Headquarters needs an `in_invoice` (Vendor Bill) with `partner_id = franchise_company.partner_id` to mirror the franchise's `out_invoice`.
2. `account.journal` search assumed every active company in multi-company setups has pre-configured journals.
3. `action_set_cancelled` implemented only a state write (`self.write({'status': 'cancelled'})`) without a lifecycle teardown method for unposted dependent records.

---

## Solution ✅

### 1. Tripartite Invoicing with Automated Journal Fallback
In the deal/TCR contracting action, generate all three documents and auto-resolve or auto-create journals defensively:

```python
def _create_commission_invoice(self, company, partner, product, amount, move_type='out_invoice'):
    """Create a DRAFT customer invoice or vendor bill defensively."""
    journal_type = 'sale' if move_type == 'out_invoice' else 'purchase'
    journal = self.env['account.journal'].sudo().search([
        ('type', '=', journal_type), ('company_id', '=', company.id)
    ], limit=1)
    
    if not journal:
        default_code = 'INV' if journal_type == 'sale' else 'BILL'
        journal_name = f"Customer Invoices - {company.name}" if journal_type == 'sale' else f"Vendor Bills - {company.name}"
        journal = self.env['account.journal'].sudo().create({
            'name': journal_name,
            'code': default_code,
            'type': journal_type,
            'company_id': company.id,
        })

    return self.env['account.move'].sudo().with_company(company).create({
        'move_type': move_type,
        'partner_id': partner.id,
        'company_id': company.id,
        'journal_id': journal.id,
        'invoice_date': fields.Date.context_today(self),
        'tcr_id': self.id,
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id,
            'name': product.display_name,
            'quantity': 1.0,
            'price_unit': amount,
            'tax_ids': [(6, 0, [])],
        })],
    })

def _generate_commission_invoices(self):
    """Contracted: Generate tripartite documents idempotently."""
    AccountMove = self.env['account.move'].sudo()
    Product = self.env['product.product'].sudo()
    Partner = self.env['res.partner'].sudo()

    for rec in self:
        if AccountMove.search_count([
            ('tcr_id', '=', rec.id),
            ('move_type', 'in', ('out_invoice', 'in_invoice'))
        ]):
            continue  # Idempotency guard

        total_commission = (rec.project / 100.0) * rec.unit_price
        if total_commission <= 0:
            continue

        product = Product.search([('commission', '=', True)], limit=1)
        lxet = rec._get_lxet_company(rec.franchise_id)

        # 1. Invoice 1: Customer Invoice in Parent Company (Customer = Developer)
        rec._create_commission_invoice(lxet, rec.developer_id, product, total_commission, move_type='out_invoice')

        # Inter-company for sub-franchise
        if rec.franchise_id and rec.franchise_id != lxet:
            cp = self.env['commission.project'].sudo().search([
                ('project_id', '=', rec.project_id.id),
                ('franchise_id', '=', rec.franchise_id.id),
            ], limit=1)
            franchise_amount = (cp.franchise_commission / 100.0) * total_commission if cp else 0.0

            if franchise_amount > 0:
                lxet_partner = Partner.search([('lxet', '=', True)], limit=1)
                # 2. Invoice 2: Customer Invoice in Franchise (Customer = LXET)
                rec._create_commission_invoice(rec.franchise_id, lxet_partner, product, franchise_amount, move_type='out_invoice')
                
                # 3. Invoice 3: Vendor Bill in Parent Company (Vendor = Franchise Partner)
                franchise_partner = rec.franchise_id.partner_id
                if franchise_partner:
                    rec._create_commission_invoice(lxet, franchise_partner, product, franchise_amount, move_type='in_invoice')
```

### 2. Deal Cancellation Teardown Guard
Prevent orphaned draft invoices and ghost commission lines:

```python
def action_set_cancelled(self):
    self._check_tcr_approval_authority()
    for rec in self:
        # 1. Check for posted commission entries and unlink drafts
        if rec.commission_lines:
            posted_moves = rec.commission_lines.mapped('move_id').filtered(lambda m: m.state == 'posted')
            if posted_moves:
                raise UserError(_("Cannot cancel: commission lines have posted entries."))
            draft_moves = rec.commission_lines.mapped('move_id').filtered(lambda m: m.state == 'draft')
            draft_moves.unlink()
            rec.commission_lines.unlink()

        # 2. Cancel and unlink draft invoices/bills
        invoices = self.env['account.move'].sudo().search([('tcr_id', '=', rec.id)])
        for inv in invoices:
            if inv.state == 'posted':
                raise UserError(_("Cannot cancel: invoice %s is posted. Reverse it first.") % inv.name)
            elif inv.state == 'draft':
                inv.button_cancel()
                inv.unlink()
                
    self.write({'status': 'cancelled'})
```

---

## ⚠️ Pitfalls

1. **Company Context (`with_company`):** Always invoke `.with_company(company)` when creating `account.move` in multi-company environments. Omitting it leads to tax, journal, or fiscal position leakage from the user's active session company.
2. **Posted Move Unlinking:** Never attempt to delete (`unlink()`) posted `account.move` or `account.move.line` records; Odoo will raise an ORM error. Always enforce manual credit notes / reversal for posted moves.
3. **Idempotency Guard Scope:** When checking if invoices were already generated on a deal, include both `out_invoice` and `in_invoice` in the domain.

---

## Verification

Run automated test verifying:
1. Franchise TCR contracted generates exactly 3 account moves (2 customer invoices + 1 vendor bill).
2. Deal cancellation deletes all draft account moves and commission lines without leaving orphaned database rows.

---

## References

- Related: `orm/money-flow-reversal-on-refund-cancel-reset-draft.md`
- Docs: `Docs/LXET_FLOW_CHARTS.html` (TC-021, TC-042)
