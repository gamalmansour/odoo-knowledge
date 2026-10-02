# Cross-Module Statutory Clearance Gate Breaks Commercial Subcontracts and Test Suites

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-19                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `statutory-clearance`, `subcontractor`, `cross-module`, `api-depends`, `gtpl`, `test-isolation`

---

## Problem

When adding statutory compliance gates (such as Saudi Government GTPL clearances for Qiwa, GOSI, ZATCA Zakat, and Commercial Registration) across subcontracting and billing modules, any progress invoice approval crashes with a `ValidationError`:

```
odoo.exceptions.ValidationError: Statutory Clearance Gate Block:
Cannot approve subcontractor progress certificate 'SUB-INV/2026/0001'.
Subcontractor 'UAT Subcontractor' has deficient or expired clearances: Commercial Registration (CR), GOSI Certificate, ZATCA Zakat Certificate, Qiwa Saudization Certificate.
Active statutory certificates are required by Saudi law before certifying payments.
```

This completely breaks:
1. Standard private commercial contracts where government GTPL regulations do not apply.
2. Unit tests and test suites (`TransactionCase`), where mock test partners do not have government compliance certificates populated.

In addition, Odoo 18 logs ORM warnings during registry loading:
```
UserWarning: Field 'res.company.country_id' in dependency of contract.subcontractor.invoice.is_clearance_blocked should be searchable.
UserWarning: res.partner: inconsistent 'store' for computed fields, accessing clearance_summary may recompute and update is_cr_valid...
```

---

## Root Cause

1. **Overly Broad Gate Scope:** The computed field `is_saudi_gtpl_governed` checked `rec.company_id.country_id.code == 'SA'`. Because the host company operates in Saudi Arabia, **every** subcontract was classified as subject to Saudi Government Tenders and Procurement Law (GTPL), even if it was a private commercial subcontract or created in an automated unit test.
2. **Unsearchable Related Field in `@api.depends`:** In Odoo core, `res.company.country_id` is a related field (`related='partner_id.country_id'`) without `store=True`. Traversing it in `@api.depends('company_id.country_id.code')` cannot be inverted into SQL for reverse trigger searches.
3. **Mixing Stored and Non-Stored Computes:** In `res.partner`, the same compute method `_compute_clearance_validity` calculated both `is_cr_valid` (`store=True`) and `clearance_summary` (`store=False`), triggering Odoo 18's warning for inconsistent store and compute_sudo.

---

## Solution ✅

### 1. Scope Statutory Gates to Contract Context, Not Company Country

Gate the statutory requirement on the project or owner contract's statutory nature, falling back safely for non-government and private contracts:

```python
# contract_subcontractor.py
is_saudi_gtpl_governed = fields.Boolean(
    string='Governed by Saudi GTPL',
    compute='_compute_is_saudi_gtpl_governed',
    store=True,
    help="True if the linked owner contract is a Saudi Government IPC (GTPL governed)."
)

@api.depends('project_id.contract_id', 'project_id.contract_id.is_saudi_government_ipc')
def _compute_is_saudi_gtpl_governed(self):
    for rec in self:
        owner_contract = rec.project_id.contract_id if rec.project_id else False
        rec.is_saudi_gtpl_governed = bool(owner_contract and getattr(owner_contract, 'is_saudi_government_ipc', False))
```

In the invoice model, clear the clearance block for non-GTPL subcontracts:

```python
# contract_subcontractor_invoice.py
for rec in self:
    is_gtpl = bool(rec.contract_id and rec.contract_id.is_saudi_gtpl_governed)
    if not is_gtpl:
        rec.cr_status = 'valid'
        rec.gosi_status = 'valid'
        rec.zakat_status = 'valid'
        rec.saudization_status = 'valid'
        rec.is_clearance_blocked = False
        continue
```

### 2. Traverse Searchable Paths in `@api.depends`

If company country must be inspected, traverse through `partner_id`:

```python
# Bad (res.company.country_id is non-stored related):
@api.depends('company_id.country_id.code')

# Good (partner_id.country_id is stored):
@api.depends('company_id.partner_id.country_id.code')
```

### 3. Separate Stored and Non-Stored Computes

Split boolean stored flags from string summary fields into distinct compute methods:

```python
# res_partner.py
is_cr_valid = fields.Boolean(compute='_compute_clearance_validity', store=True)
clearance_summary = fields.Char(compute='_compute_clearance_summary')

@api.depends('cr_number', 'cr_expiry', 'gosi_cert_expiry', ...)
def _compute_clearance_validity(self):
    today = fields.Date.today()
    for partner in self:
        partner.is_cr_valid = bool(partner.cr_number and partner.cr_expiry and partner.cr_expiry >= today)

@api.depends('is_cr_valid', 'is_gosi_valid', ...)
def _compute_clearance_summary(self):
    for partner in self:
        partner.clearance_summary = _("Valid") if partner.is_all_clearance_valid else _("Non-Compliant")
```

---

## ⚠️ Pitfalls

- **Gate Placement in Method Overrides:** When extending `action_approve()`, always invoke `super().action_approve()` **first** before evaluating clearance blocks. This ensures standard security group checks (e.g. only Contract Managers can approve) happen before domain validation logic.
- **Related Fields on Extension Models:** When extending child models with multi-company rules, ensure `company_id` is defined as a stored related field (`company_id = fields.Many2one(related='contract_id.company_id', store=True)`). If adding this to existing tables with active records, execute `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` if upgrading live.

---

## Verification

Run the test suite in Odoo shell:

```bash
python3 odoo-bin shell -c odoo18_dev.conf -d odoo18_construction << 'EOF'
import unittest
from odoo.addons.construction_contract.tests.test_subcontractor_cycle import TestSubcontractorCycle
suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSubcontractorCycle)
res = unittest.TextTestRunner(verbosity=2).run(suite)
assert len(res.failures) == 0 and len(res.errors) == 0
EOF
```

---

## References

- Related file: `orm/missing-company-id-subcontract-model-preload-error.md`
- Related file: `orm/inconsistent-store-compute-sudo-computed-fields.md`
