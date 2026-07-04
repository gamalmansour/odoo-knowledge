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

> When updating address fields (`street`, `city`, `zip`, etc.) on `res.partner`, the `partner_latitude` and `partner_longitude` fields are automatically reset to `0.0`. This breaks custom integrations or modules that rely on static imported coordinates (like sale visit modules restricting visits to a specific radius). Additionally, clicking the "Geolocate" button overwrites the precise imported coordinates with generalized ones.

## Root Cause

> The `base_geolocalize` module overrides the `write` method on `res.partner`. If it detects any address field in the `vals` dictionary, and the `latitude` and `longitude` are not explicitly included in the `vals`, it assumes the old coordinates are invalid and forcefully adds `{'partner_latitude': 0.0, 'partner_longitude': 0.0}` to `vals` before calling `super()`.
> It also provides a `geo_localize` method that fetches coordinates from Google Maps and overwrites the existing coordinates.

## Solution ✅

> Override the `write` method in your custom module to take a backup of the coordinates before `super()`, and then restore them after `super()` if they were reset to `0.0`. This "Backup and Restore" pattern is 100% immune to MRO (Method Resolution Order) issues, meaning it will work regardless of whether your module loads before or after `base_geolocalize`.
> 
> Also, override the `geo_localize` method to return `True` so that Odoo's automated geolocation never updates the coordinates. Finally, hide the "Compute based on address" button in the view so users don't get confused when clicking it does nothing.

### 1. Python Override

```python
# -*- coding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        """
        Prevent ANY implicit change to latitude and longitude when address fields are modified.
        This restores the original coordinates whether they were zeroed out or changed to another value.
        """
        address_fields = ['street', 'zip', 'city', 'state_id', 'country_id']
        
        # If address is modified, we protect the coordinates
        if any(field in vals for field in address_fields):
            # 1. Backup original coordinates
            coords_backup = {p.id: (p.partner_latitude, p.partner_longitude) for p in self}
            
            # Check if user explicitly provided NON-ZERO coordinates in this update.
            # (If base_geolocalize injected 0.0, this will be False).
            explicit_manual_update = False
            if 'partner_latitude' in vals or 'partner_longitude' in vals:
                lat = vals.get('partner_latitude', 0.0)
                lon = vals.get('partner_longitude', 0.0)
                if lat and lat != 0.0 or lon and lon != 0.0:
                    explicit_manual_update = True
            
            # 2. Call super
            res = super(ResPartner, self).write(vals)
            
            # 3. If no explicit manual update, enforce the backup
            if not explicit_manual_update:
                for p in self:
                    old_lat, old_lon = coords_backup[p.id]
                    new_lat, new_lon = p.partner_latitude, p.partner_longitude
                    
                    # If it changed to ANYTHING (0.0 or something else)
                    if new_lat != old_lat or new_lon != old_lon:
                        super(ResPartner, p).write({
                            'partner_latitude': old_lat,
                            'partner_longitude': old_lon
                        })
            return res
            
        return super(ResPartner, self).write(vals)

    def geo_localize(self):
        """
        Completely disable the auto-geolocation feature so that it NEVER 
        updates coordinates based on the address automatically.
        """
        return True
```

### 2. XML View Override

Hide the geolocalize buttons from the UI completely:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_partner_form_inherit_geo_hide" model="ir.ui.view">
        <field name="name">res.partner.form.inherit.geo.hide</field>
        <field name="model">res.partner</field>
        <field name="inherit_id" ref="base_geolocalize.view_crm_partner_geo_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='geo_localize_button']" position="attributes">
                <attribute name="invisible">1</attribute>
            </xpath>
        </field>
    </record>
</odoo>
```

## ⚠️ Pitfalls

- **Performance with Bulk Updates:** Because this solution loops through `self` and triggers `super().write()` per partner, it may introduce a slight performance overhead during massive bulk address updates. However, address updates are rarely done in bulk outside of migrations.

## Verification

> Update the `street` field of a customer that has valid latitude and longitude. The latitude and longitude should remain exactly the same. Clicking "Geolocate" on the partner form should also do nothing.
