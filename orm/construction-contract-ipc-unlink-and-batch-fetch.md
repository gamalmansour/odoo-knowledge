# Construction Contracts: Unlink Protection on Certified Records and O(1) Batch BOQ Fetching

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-10                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `contract`, `ipc`, `unlink`, `batch-fetch`, `n+1-queries`, `subcontract`

---

## Problem

In construction management ERPs handling Owner Interim Payment Certificates (IPCs) and Subcontractor Payment Applications:
1. **Silent Audit Trail Destruction**: Users could delete contracts and certified progress invoices (`contract.owner`, `contract.subcontractor`, `contract.progress.invoice`, `contract.subcontractor.invoice`) even after approval or posting of associated financial customer invoices/vendor bills, leaving orphaned `account.move` and analytical entries.
2. **N+1 Performance Bottleneck during BOQ Fetching**: When generating a payment application with 500+ BOQ lines, looping `search()` queries inside `for line in contract.line_ids:` caused quadratic database roundtrips, connection timeouts, and locking.

## Root Cause

1. Missing `unlink()` overrides on contract and certificate models to enforce state checks (`state not in ('draft', 'cancelled')`) and verify whether posted downstream `account.move` records exist.
2. Naive per-line query iteration (`search()` in a loop) instead of pre-fetching cumulative executed quantities in a single batched query using dictionary mapping.

## Solution ✅

### 1. Unlink Protection on Contracts and Certificates

Enforce strict business blocks preventing record deletion once workflows have commenced or certificates have been approved:

```python
def unlink(self):
    for rec in self:
        if rec.state not in ('draft', 'cancelled'):
            raise UserError(_("You cannot delete a contract that is in '%s' status. You must cancel it first.") % rec.state)
    return super().unlink()
```

For progress certificates linked to accounting entries:

```python
def unlink(self):
    for rec in self:
        if rec.state in ('approved', 'invoiced'):
            raise UserError(_("You cannot delete an approved or invoiced certificate (%s). Reset it to draft first.") % rec.name)
        if rec.account_move_id and rec.account_move_id.state == 'posted':
            raise UserError(_("You cannot delete a payment application (%s) linked to a posted vendor bill.") % rec.name)
    return super().unlink()
```

### 2. O(1) Batch BOQ Fetching

Pre-fetch prior certified lines in a single query before iterating through contract BOQ items:

```python
def action_fetch_boq(self):
    self.ensure_one()
    if self.state != 'draft':
        raise ValidationError(_('You can only fetch BOQ lines in draft state.'))
    
    self.line_ids.unlink()

    # Pre-fetch all previous approved/invoiced subcontractor lines in ONE query
    previous_invoices = self.search([
        ('contract_id', '=', self.contract_id.id),
        ('state', 'in', ['approved', 'invoiced']),
        ('id', '!=', self.id),
    ])
    prev_qty_map = {}
    if previous_invoices:
        prev_lines = self.env['contract.subcontractor.invoice.line'].search([
            ('progress_invoice_id', 'in', previous_invoices.ids),
        ])
        for pl in prev_lines:
            if pl.boq_line_id:
                prev_qty_map[pl.boq_line_id.id] = prev_qty_map.get(pl.boq_line_id.id, 0.0) + pl.current_qty

    # Build line values list and insert in a single create() call
    lines_to_create = []
    for line in self.contract_id.line_ids:
        if line.display_type:
            lines_to_create.append({
                'progress_invoice_id': self.id,
                'boq_line_id': line.id,
                'name': line.name,
                'display_type': line.display_type,
                'sequence': line.sequence,
            })
        else:
            lines_to_create.append({
                'progress_invoice_id': self.id,
                'boq_line_id': line.id,
                'name': line.name,
                'total_qty': line.qty,
                'unit_price': line.unit_price,
                'previous_qty': prev_qty_map.get(line.id, 0.0),
                'current_qty': 0.0,
                'sequence': line.sequence,
            })

    if lines_to_create:
        self.env['contract.subcontractor.invoice.line'].create(lines_to_create)
```

## ⚠️ Pitfalls

- **Do NOT delete draft payment certificates if downstream bills were posted:** Always inspect `account_move_id.state` before allowing deletion.
- **Section & Note lines:** Section header and note rows (`display_type in ('line_section', 'line_note')`) have no quantity and no BOQ calculation; skip them when mapping quantities to prevent `TypeError` or zero division.
- **Multi-Company isolation:** When pre-fetching prior lines, ensure record rules or company filters are preserved so lines from other subsidiaries do not leak into cumulative calculations.

## Verification

Run unit tests asserting that:
1. `contract.unlink()` raises `UserError` when called on non-draft records.
2. `action_fetch_boq()` executes exactly 2 queries regardless of whether the BOQ has 10 lines or 1,000 lines.
