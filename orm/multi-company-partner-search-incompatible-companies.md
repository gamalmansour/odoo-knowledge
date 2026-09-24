# Multi-Company Partner Search Triggers Incompatible Companies Error on Invoicing

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `multi-company`, `res.partner`, `account.move`, `_check_company`, `invoicing`

---

## Problem

When programmatically generating inter-company or cross-franchise invoices (e.g. from a sub-franchise to the parent holding company), searching for a partner using a flag or name without filtering by `company_id` can return a partner explicitly bound to another company. This triggers Odoo's `_check_company` guard during invoice creation:

```python
odoo.exceptions.UserError: Incompatible companies on records:
- "Draft Invoice" belongs to company "Test Franchise" and "Partner" (partner_id: 'LXET Egypt') belongs to another company.
- "Draft Invoice" belongs to company "Test Franchise" and "Commercial Entity" (commercial_partner_id: 'LXET Egypt') belongs to another company.
```

## Root Cause

`Partner.search([('flag', '=', True)], limit=1)` executes a global search. If the target partner has `company_id = X` (e.g. the main headquarters company), attempting to create an `account.move` on company `Y` (a sub-franchise or branch) with that partner violates Odoo's record company consistency rule (`_check_company`).

## Solution ✅

When searching for a partner to use on documents for a specific company (`rec.franchise_id`), scope the search to allow either global partners (`company_id = False`) or partners explicitly bound to the document's company (`company_id = rec.franchise_id.id`), before falling back to a global match:

```python
# In models/commission_tcr.py or any document generator
lxet_partner = Partner.search([
    ('lxet', '=', True),
    ('company_id', 'in', [False, rec.franchise_id.id]),
], limit=1) or Partner.search([('lxet', '=', True)], limit=1)

if not lxet_partner:
    raise UserError(_("Flag a partner as 'LXET' before contracting a sub-franchise TCR."))

rec._create_commission_invoice(
    rec.franchise_id, lxet_partner, product, franchise_amount
)
```

Additionally, in multi-company setups, parent holding company contacts intended to interact across all branches should ideally have `company_id = False` (shared contact).

## ⚠️ Pitfalls

- Never assume `limit=1` returns a partner compatible with the current company context in multi-company databases.
- Multi-company unit tests using `TransactionCase` frequently create temporary companies; un-scoped searches will inadvertently fetch pre-existing production/demo partners from other companies.

## Verification

Run test suites that execute invoice generation under sub-companies:
```bash
python3 odoo-bin -c lexies.conf -d <dbname> --test-enable --test-tags=/sb_commission_enhancement --stop-after-init --http-port=2626
```
Confirm 0 errors and 0 failures.
