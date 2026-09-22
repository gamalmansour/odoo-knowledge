# FIDIC Clause 13.8 Subcontractor Price Escalation & Variation Order BOQ Synchronization

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `contracts`, `fidic-13.8`, `price-escalation`, `variation-orders`, `boq-sync`, `snapshots`, `vendor-bills`, `odoo18`

---

## Problem

In enterprise construction contracts, two high-risk financial and contractual operations frequently trigger disputes, duplicate accounting entries, or budget distortions:

1. **Variation Orders (Change Requests) Scope Desynchronization:**
   When client-approved Variation Orders (VO) are not synchronized directly into operational Project BOQs, site engineers execute work orders against non-existent or stale BOQ quantities. Furthermore, manual re-entry of VO items causes duplicate entries or accidental budget double-counting when amendments are drafted.
2. **Subcontractor Price Fluctuation Disputes (FIDIC Clause 13.8):**
   Subcontractors working on long-duration infrastructure projects (2-5 years) face commodity price fluctuations (Rebar Steel, Ready-Mix Concrete, Bitumen, Copper Cables, Diesel). If progress invoices compute escalation dynamically from live index tables without freezing the underlying parameters, any retrospective revision or restatement of government published indices destroys auditability and leads to legal disputes.

---

## Root Cause

1. **Lack of Idempotent BOQ Synchronization:**
   Change request workflows that lack an explicit technical execution flag (`boq_updated`) allow multiple clicks of "Apply" or re-approvals to inflate project BOQ quantities multiple times.
2. **Unvalidated Formula Polynomials:**
   FIDIC Clause 13.8 requires that the fixed proportion $a$ plus all variable weightings $\sum b$ must equal exactly $1.0000$. If contracts allow unconstrained weighting inputs (e.g. $0.15 + 0.50 + 0.40 = 1.05$), every certificate silently overbills or underbills.
3. **Overriding Computed Stored Fields Without Full Dependency Scope:**
   Overriding `_compute_financials` on progress invoice models to incorporate `escalation_amount` without including the parent model's full list of `@api.depends` fields causes Odoo 18 to freeze parent stored computations or fail to recompute `net_payable`.

---

## Solution ✅

### 1. Idempotent Project BOQ Synchronization with Scope Classification

Categorize each variation line into `addition`, `deduction`, or `new_item`. Maintain a strict `boq_updated` boolean flag and log audit trails on both the Change Request and the Project chatter:

```python
def action_apply_to_project_boq(self) -> None:
    self.ensure_one()
    if self.state not in ('tech_approved', 'client_approved', 'converted'):
        raise UserError(_("Variation Order must be approved before applying changes to the Project BOQ."))
    if self.boq_updated:
        raise UserError(_("Variation Order scope has already been applied to the Project BOQ."))

    project = self.project_id
    applied_lines_log = []

    for line in self.line_ids:
        if line.variance_type == 'new_item' or not line.boq_item_id:
            new_code = f"VO-{self.name}-{line.id}"
            new_item = self.env['project.boq.item'].create({
                'project_id': project.id,
                'code': new_code,
                'name': line.description or line.product_id.name,
                'uom_id': line.uom_id.id if line.uom_id else line.product_id.uom_id.id,
                'quantity': abs(line.requested_qty),
                'unit_price': line.requested_unit_price,
                'budget_amount': line.estimated_cost,
                'execution_method': 'direct',
            })
            line.boq_item_id = new_item.id
            applied_lines_log.append(f"• Added New BOQ Item [{new_code}] {new_item.name}: {new_item.quantity}")
        elif line.variance_type == 'addition':
            line.boq_item_id.quantity += abs(line.requested_qty)
        elif line.variance_type == 'deduction':
            line.boq_item_id.quantity = max(0.0, line.boq_item_id.quantity - abs(line.requested_qty))

    if hasattr(project, 'contract_value') and self.requested_client_price:
        project.contract_value += self.requested_client_price
    if hasattr(project, 'direct_cost_budget') and self.estimated_internal_cost:
        project.direct_cost_budget += self.estimated_internal_cost

    self.boq_updated = True
    self.boq_update_date = fields.Date.today()
```

### 2. FIDIC Clause 13.8 Weighting Constraint & Snapshot Lines

Enforce strict polynomial validation ($a + \sum b = 1.0000$) using `float_compare` at 4 decimal precision:

```python
@api.constrains('escalation_enabled', 'escalation_fixed_portion', 'escalation_coefficient_ids')
def _check_escalation_formula(self) -> None:
    for rec in self:
        if not rec.escalation_enabled:
            continue
        weights_sum = sum(rec.escalation_coefficient_ids.mapped('weight'))
        total = rec.escalation_fixed_portion + weights_sum
        if float_compare(total, 1.0, precision_digits=4) != 0:
            raise ValidationError(_(
                "Escalation formula must total 1.0: "
                "Fixed portion %(fixed).4f + Weights %(weights).4f = %(total).4f.",
                fixed=rec.escalation_fixed_portion, weights=weights_sum, total=total
            ))
```

Freeze indices at calculation time into an immutable snapshot model (`contract.subcontractor.ipc.escalation.line`):

```python
def action_compute_escalation(self) -> None:
    for rec in self:
        contract = rec.contract_id
        factor = contract.escalation_fixed_portion or 0.0
        snapshot_lines = [(5, 0, 0)]

        for coef in contract.escalation_coefficient_ids:
            base = coef.index_id._value_at(contract.escalation_base_date)
            current = coef.index_id._value_at(rec.date)
            if not base or not current:
                raise UserError(_("Index '%s' missing published values.") % coef.index_id.name)
            ratio = current.value / base.value
            factor += coef.weight * ratio
            snapshot_lines.append((0, 0, {
                'index_id': coef.index_id.id,
                'weight': coef.weight,
                'base_value': base.value,
                'current_value': current.value,
            }))

        rec.escalation_line_ids = snapshot_lines
        rec.escalation_amount = rec.gross_amount * (factor - 1.0)
```

---

## ⚠️ Pitfalls to Avoid

1. **Never Recompute Archived/Certified Certificates:**
   Escalation adjustments must be frozen once certified. If monthly index figures are subsequently revised by GASTAT, adjustments must be booked as separate true-up lines in subsequent certificates, never by overwriting historical IPCs.
2. **Decouple Many2one Relations Before Unlinking During Reversion:**
   When writing `action_revert_from_project_boq()`, always set `line.boq_item_id = False` BEFORE calling `item_to_delete.unlink()`. Failing to clear the relation first causes PostgreSQL foreign key conflicts or triggers cascading validation errors during ORM recomputes.
3. **Vendor Bill Synchronization:**
   Ensure `action_create_vendor_bill()` checks `if rec.escalation_amount != 0.0` and appends an escalation line directly into `account_move_id` to prevent discrepancies between Subcontractor IPC ledger and General Ledger Accounts Payable.
