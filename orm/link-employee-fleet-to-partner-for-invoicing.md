# 🧾 Linking Employee & Fleet to Partner for Vendor Bills

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟢 Low                                    |
| Last Verified | 2026-06-03                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `partner`, `invoice`, `vendor-bill`, `hr.employee`, `fleet.vehicle`

---

## Problem

> When trying to programmatically generate a Vendor Bill (`account.move` with type `in_invoice`) for an Employee (`hr.employee`) or a Vehicle (`fleet.vehicle`), Odoo requires a `partner_id`. 
> While `hr.employee` has `address_home_id` (Private Address) and `fleet.vehicle` has `driver_id`, using these directly for accounting is dangerous. The Private Address might not be set, and the driver might not be the actual owner/vendor you owe money to.

## Root Cause

> Standard models don't tightly couple to an accounting partner for commission/rental purposes out of the box. Relying on implicit fields like `address_home_id` can lead to `UserError` or incorrect accounting entries if the HR data is incomplete or used for a different purpose.

## Solution ✅

> Explicitly add a `commission_partner_id` (or similar `vendor_partner_id`) to both `hr.employee` and `fleet.vehicle` to clearly delineate who receives the vendor bill.

```python
# In models/hr_employee.py
from odoo import fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    commission_partner_id = fields.Many2one(
        "res.partner",
        string="Commission Partner",
        help="Partner to be used when creating vendor bills for event commissions.",
        tracking=True,
    )
```

```python
# In models/fleet_vehicle.py
from odoo import fields, models

class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    commission_partner_id = fields.Many2one(
        "res.partner",
        string="Commission Partner",
        help="Partner to be used when creating vendor bills for event commissions.",
        tracking=True,
    )
```

In your bill generation logic, you fetch this field instead of `address_home_id` and raise a clear error if it's missing:

```python
        partner = self.helper_id.commission_partner_id
        if not partner:
            raise UserError(_("Please set a Commission Partner on the helper's employee profile."))
```

## ⚠️ Pitfalls

- **Do NOT reuse `address_home_id` for vendor bills:** HR uses it for completely different things (like private contact info, emergency contacts), and it might be empty.
- **Do NOT reuse `driver_id` for vendor bills:** The driver might be an employee of the boat company, not the entity you owe money to.

## Verification

> Check that the new fields appear in the UI and test generating a bill without them to ensure the `UserError` catches it cleanly before Odoo throws a traceback.
