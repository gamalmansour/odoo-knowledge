# Restoring `res.partner.company_type` Compute/Inverse When Overridden by Another Addon

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `res.partner`, `company_type`, `is_company`, `compute`, `inverse`, `inheritance`, `eta`, `e-invoice`

---

## Problem

Switching a Contact between **Individual** and **Company** (or setting a custom `partner_type` such as `developer` vs `client`) stops updating `is_company`, or `company_type` and `is_company` fall out of sync in the database (e.g., `company_type = 'company'` while `is_company = False`, or vice versa).

This breaks downstream accounting, invoicing, and tax-authority integrations (such as Egyptian ETA e-Invoice for companies vs e-Receipt for individuals) as well as standard Odoo views and domains that filter on `is_company`.

## Root Cause

In core Odoo (`addons/base/models/res_partner.py`), `company_type` is a non-stored computed field backed by `is_company` via `compute='_compute_company_type'` and `inverse='_write_company_type'`.

When a third-party or colleague addon redefines `company_type` naively as a plain stored `Selection` field:

```python
# Anti-pattern in third-party addon — silently strips compute & inverse!
company_type = fields.Selection(
    [('person', 'Individual'), ('company', 'Company')],
    string='Company Type',
)
```

Odoo replaces the field definition with a plain stored column that has **no `compute` and no `inverse`**, permanently breaking the synchronization between `company_type` and `is_company`.

## Solution ✅

In your own standalone addon (listing the offending addon in `depends` so your inheritance loads after it), explicitly restore `compute`, `inverse`, and `store=True` (keeping `store=True` prevents dropping an existing DB column created by the other addon), and enforce any business-type mapping consistently across `onchange`, `create`, and `write`:

```python
from typing import Any

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Restore compute/inverse broken by another addon redefining company_type as plain Selection.
    company_type = fields.Selection(
        selection=[('person', 'Individual'), ('company', 'Company')],
        string='Company Type',
        compute='_compute_company_type',
        inverse='_write_company_type',
        store=True,
    )

    @api.depends('is_company')
    def _compute_company_type(self) -> None:
        for partner in self:
            partner.company_type = 'company' if partner.is_company else 'person'

    def _write_company_type(self) -> None:
        for partner in self:
            partner.is_company = partner.company_type == 'company'

    @staticmethod
    def _resolve_is_company_from_classification(
        partner_type: str | bool | None,
        is_lxet: bool,
    ) -> bool | None:
        if is_lxet or partner_type == 'developer':
            return True
        if partner_type in ('client', 'resale'):
            return False
        return None

    @api.onchange('partner_type', 'lxet', 'company_type', 'is_company')
    def _onchange_gm_partner_classification(self) -> None:
        for partner in self:
            enforced = self._resolve_is_company_from_classification(
                partner.partner_type, bool(partner.lxet)
            )
            if enforced is not None:
                partner.is_company = enforced
                partner.company_type = 'company' if enforced else 'person'
```

Also enforce the same rule in `create()` and `write()` so RPC calls or manual clicks on the `Individual / Company` radio widget cannot leave `company_type` and `is_company` contradicting the business classification.

## ⚠️ Pitfalls

- **Load order matters:** You MUST include the offending module in your `__manifest__.py` `depends` list; otherwise your restored `compute`/`inverse` may load *before* the broken plain `Selection` and be overwritten again.
- **Do NOT drop `store=True` if the column already exists:** If another addon already made `company_type` stored in PostgreSQL, keeping `store=True` with `@api.depends('is_company')` avoids schema conflicts and keeps SQL domains/reports fast.
- **Avoid a global `default='client'` on `res.partner.partner_type`:** Setting a global default on `res.partner` fires when Odoo creates internal user partners or company partners during signup/company creation, which can trip phone/mobile constraints meant only for CRM clients. Pass `default_partner_type='client'` via CRM Lead `_prepare_customer_values()` and view field `context` instead.
- **Existing historical rows:** Restoring the field fixes all new creates/writes; provide an idempotent Server Action to realign legacy rows rather than mutating production data inside a `post_init_hook`.

## Verification

```python
dev = env['res.partner'].create({'name': 'Test Dev', 'partner_type': 'developer'})
assert dev.is_company is True and dev.company_type == 'company'

client = env['res.partner'].create({'name': 'Test Client', 'partner_type': 'client', 'phone': '01012345678', 'is_company': True})
assert client.is_company is False and client.company_type == 'person'

# Attempting manual contradiction via write() stays consistent
client.write({'company_type': 'company', 'is_company': True})
assert client.is_company is False and client.company_type == 'person'
```

## References

- Core Odoo definition: `addons/base/models/res_partner.py` (`_compute_company_type`, `_write_company_type`)
- Related file: `orm/stored-compute-incomplete-depends-silent-staleness.md`
