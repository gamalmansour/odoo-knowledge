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

> Override the `write` method in your custom module to backup the coordinates before calling `super()`, and then restore them if they were reset to `0.0` by `base_geolocalize`.

```python
# -*- coding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        """
        Prevent base_geolocalize from resetting latitude and longitude to 0.0
        when address fields are modified, to keep the coordinates fixed for visits.
        """
        address_fields = ['street', 'zip', 'city', 'state_id', 'country_id']
        
        # If any address field is modified and coordinates are not explicitly passed
        if any(field in vals for field in address_fields) and not all('partner_%s' % field in vals for field in ['latitude', 'longitude']):
            # Backup current coordinates
            coords_backup = {
                partner.id: (partner.partner_latitude, partner.partner_longitude)
                for partner in self
            }
            
            res = super(ResPartner, self).write(vals)
            
            # Restore the coordinates if they were zeroed out
            for partner in self:
                old_lat, old_long = coords_backup.get(partner.id, (0.0, 0.0))
                # Only restore if base_geolocalize zeroed them out and old values were not zero
                if partner.partner_latitude == 0.0 and partner.partner_longitude == 0.0:
                    if old_lat != 0.0 or old_long != 0.0:
                        super(ResPartner, partner).write({
                            'partner_latitude': old_lat,
                            'partner_longitude': old_long,
                        })
            return res
            
        return super(ResPartner, self).write(vals)
```

## ⚠️ Pitfalls

- **Avoid Recursion/Loop issues:** When restoring the coordinates using `super(ResPartner, partner).write(...)`, make sure you use `super` instead of `partner.write` to avoid recursive loop execution of all override methods.
- **Recordsets:** Since `write` operates on a recordset (`self`), backing up coordinates per `partner.id` in a dictionary ensures it safely scales for multi-record operations.

## Verification

> Update the `street` field of a customer that has valid latitude and longitude. The latitude and longitude should remain the same and not change to 0.0.
