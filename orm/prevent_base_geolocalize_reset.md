# Prevent base_geolocalize from Resetting Coordinates

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | 15, 16, 17, 18, 19                         |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-04                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `res.partner`, `base_geolocalize`, `latitude`, `longitude`, `write_override`

---

## Problem

> When updating address fields (`street`, `city`, `zip`, etc.) on `res.partner`, the `partner_latitude` and `partner_longitude` fields are automatically reset to `0.0`. This breaks custom integrations or modules that rely on static imported coordinates (like sale visit modules restricting visits to a specific radius).

## Root Cause

> The `base_geolocalize` module overrides the `write` method on `res.partner`. If it detects any address field in the `vals` dictionary, and the `latitude` and `longitude` are not explicitly included in the `vals`, it assumes the old coordinates are invalid and forcefully adds `{'partner_latitude': 0.0, 'partner_longitude': 0.0}` to `vals` before calling `super()`.

## Solution ✅

> Override the `write` method in your custom module to inject the current coordinates into `vals` per partner. This forces the `base_geolocalize` condition to evaluate to False, completely bypassing the reset logic.

```python
# -*- coding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        """
        Prevent base_geolocalize from resetting latitude and longitude to 0.0
        when address fields are modified, by explicitly injecting the existing coordinates
        if they aren't provided in vals.
        """
        address_fields = ['street', 'zip', 'city', 'state_id', 'country_id']
        
        # If any address field is in vals, and new coordinates are NOT explicitly provided
        if any(field in vals for field in address_fields) and not all('partner_%s' % field in vals for field in ['latitude', 'longitude']):
            res = True
            for partner in self:
                partner_vals = dict(vals)
                # Inject current coordinates to bypass base_geolocalize's reset condition
                partner_vals['partner_latitude'] = partner.partner_latitude or 0.0
                partner_vals['partner_longitude'] = partner.partner_longitude or 0.0
                
                # Call super with the updated dictionary for this specific partner
                res &= super(ResPartner, partner).write(partner_vals)
            return res
            
        return super(ResPartner, self).write(vals)
```

## ⚠️ Pitfalls

- **Performance with Bulk Updates:** Because this solution loops through `self` and triggers `super().write()` per partner, it may introduce a slight performance overhead during massive bulk address updates. However, address updates are rarely done in bulk outside of migrations.

## Verification

> Update the `street` field of a customer that has valid latitude and longitude. The latitude and longitude should remain exactly the same and the `base_geolocalize` write logic is completely bypassed.
