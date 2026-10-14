# Automated Site Delivery MIR Generation & Issuance Quality Gate

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | Best Practices                             |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-10-14                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `construction`, `qaqc`, `quality-gate`, `stock-picking`, `mir`, `material-issue`, `work-order`, `override`, `requires-qc`

---

## Problem

In large-scale construction projects, procurement and material logistics typically run much faster than QA/QC approval cycles. When materials arrive at the job site (either via direct vendor delivery or transferred from the central staging warehouse), site crews often immediately consume them on active Work Orders or Store Issues without waiting for QA/QC inspection and consultant approval.

When substandard materials (e.g., non-compliant rebar tensile strength, out-of-spec cement batches, uncertified electrical conduits) are built into the structure, discovering the failure later requires:
1. Massive structural rework, demolition, and severe contractual delay penalties.
2. Disputed subcontractor backcharges and unresolved non-conformance reports (NCRs).
3. Client consultant rejection of payment applications (IPCs).

Conversely, implementing a naive "blind hard stop" can completely paralyze site operations:
- Non-critical consumables (e.g., binding wire, screws, nails, geotextile cloth, masking tape) get blocked awaiting formal lab tests.
- Emergency structural operations (e.g., unexpected night pours or urgent shoring) cannot proceed if the consultant QA/QC engineer is unavailable to sign off an MIR in the software.

## Root Cause

1. **Decoupled Workflows:** In standard Odoo, Inventory (`stock.picking`) operates completely decoupled from Quality/Inspection (`qc.inspection.request`). Validating a stock receipt does not alert or mandate a Material Inspection Request (MIR).
2. **Missing Quality Gate at Consumption Point:** Material issuance in construction operations (`project.material.issue`, `construction.store.issue`, `project.work.order`) validates only physical stock availability, never verifying inspection approval state.
3. **Lack of Granular Categorization & Emergency Exceptions:** Without a product-level `requires_qc` toggle and a documented managerial override mechanism, teams either abandon the QC module entirely or run unauthorized shadow workflows.

## Solution ✅

Implement a robust, bidirectional **Construction Quality Gate** spanning `stock.picking`, `qc.inspection.request`, and `project.material.issue`:

### 1. Product-Level QC Exemption Configuration
Add a control boolean on `product.template` (default `True`):
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    requires_qc = fields.Boolean(
        string="Requires QC Inspection",
        default=True,
        help="If enabled, this material must pass QA/QC inspection (MIR) upon delivery to site before it can be issued to work orders or store issues."
    )
```

### 2. Automated Site Delivery MIR Triggering on `stock.picking`
Override `button_validate()` to inspect incoming receipts or internal site transfers. For any storable product with `requires_qc=True` delivered to a project location, automatically generate a draft `qc.inspection.request`:
```python
def button_validate(self):
    res = super().button_validate()
    for picking in self:
        # Detect destination project from picking or location
        project = picking.project_id
        if not project and picking.location_dest_id:
            project = self.env['construction.project'].search([
                '|',
                ('location_id', '=', picking.location_dest_id.id),
                ('warehouse_id.lot_stock_id', '=', picking.location_dest_id.id)
            ], limit=1)

        if not project:
            continue

        for move in picking.move_ids.filtered(lambda m: m.state == 'done' and m.product_id.type == 'product' and m.product_id.requires_qc):
            existing_mir = self.env['qc.inspection.request'].search([
                ('picking_id', '=', picking.id),
                ('product_id', '=', move.product_id.id),
            ], limit=1)
            if not existing_mir:
                self.env['qc.inspection.request'].create({
                    'name': f"MIR-{picking.name}-{move.product_id.default_code or move.product_id.name}",
                    'request_type': 'material',
                    'project_id': project.id,
                    'picking_id': picking.id,
                    'product_id': move.product_id.id,
                    'state': 'draft',
                })
    return res
```

### 3. Strict Issuance Quality Gate with Managerial Override
In `project.material.issue.action_issue_material()`, enforce the gate:
- If `line.product_id.requires_qc` is `False` $\rightarrow$ Pass.
- If the parent document has `qc_override=True` $\rightarrow$ Log override note and Pass.
- Otherwise, search for an approved MIR for this product and project:
```python
approved_mir = self.env['qc.inspection.request'].search([
    ('project_id', '=', issue.project_id.id),
    ('product_id', '=', line.product_id.id),
    ('request_type', '=', 'material'),
    ('state', 'in', ['approved', 'closed']),
], limit=1)

if not approved_mir:
    raise UserError(_(
        "Quality Gate Block: Cannot issue material '%(prod)s' on project '%(proj)s'. "
        "No approved Material Inspection Request (MIR) found. "
        "Material must be inspected and approved by QA/QC before issuance, or authorized via QC Override.",
        prod=line.product_id.display_name,
        proj=issue.project_id.display_name,
    ))
```

### 4. Emergency Managerial Override & Audit Trail
Allow Project Managers or QC Managers to authorize an emergency bypass:
```python
def action_authorize_qc_override(self):
    self.ensure_one()
    if not (self.env.user.has_group('construction_project.group_project_manager') or
            self.env.user.has_group('construction_qaqc.group_qc_manager')):
        raise AccessError(_("Only a Project Manager or QC Manager can authorize a QC Override."))
    self.write({
        'qc_override': True,
        'qc_override_by': self.env.user.id,
        'qc_override_date': fields.Datetime.now(),
    })
    self.message_post(body=_("⚠️ Emergency QC Override authorized by %s.") % self.env.user.name)
```

## ⚠️ Pitfalls

1. **Idempotence on Multiple Validations:** Always verify that an MIR does not already exist for `(picking_id, product_id)` before creating one to prevent duplicate requests when pickings have backorders or split moves.
2. **Product Type Filtering:** Only storable products (`type == 'product'`) require physical warehouse delivery inspections; services and consumables should not generate stock inspection records.
3. **Cross-Module Hierarchy:** Do not add store issue dependencies into the QA/QC base module. Place the inspection gate in `project.material.issue` (inside `construction_qaqc`), allowing both `project.work.order` and `construction.store.issue` to inherit the behavior cleanly without circular dependencies.
4. **Audit Trail Immutability:** Never allow clearing `qc_override_by` or `qc_override_date` silently. Any revocation or re-authorization must post an explicit message in the OpenChatter thread.

## Verification

Run automated test suite covering all four quality gate states:
```bash
odoo-bin -c odoo18_con.conf -d cons_demo --test-enable --stop-after-init -i construction_store_issue --test-tags construction_store_issue
```

Expected result:
- Unapproved material without override $\rightarrow$ Raises `UserError` (Blocked).
- Consumable item (`requires_qc = False`) $\rightarrow$ Issues successfully without MIR.
- Approved MIR $\rightarrow$ Issues successfully.
- Emergency override authorized by Manager $\rightarrow$ Issues successfully with chatter audit.

## References

- Related: `Best Practices/construction-suite-cross-module-data-coherence-and-e2e-testing.md`
- Module: `construction_qaqc` (v18.0.1.3.0)
- Module: `construction_store_issue` (v18.0.1.4.1)
