# Geolocation Coordinates Precision Digits

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | orm                                        |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-07-05                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `orm`, `fields`, `float`, `geolocation`, `precision`, `digits`

---

## Problem

> When defining custom fields for latitude and longitude (e.g. `visit_latitude`, `visit_longitude`), using the default precision or a low precision like `digits=(10, 7)` can result in inaccurate mapping on the front-end or loss of coordinates accuracy, as some maps expect up to 15 decimal places for precise location tracking.

## Root Cause

> Standard float fields might round up the coordinates if the provided `digits` tuple does not allocate enough decimal places. For geolocation, 7 decimal places is often sufficient for practical use (approx 1cm precision), but sometimes external APIs or specific tracking requirements demand up to 15 decimal places. Since longitude can go up to 180 and latitude up to 90, we need 3 digits for the integer part, plus 15 digits for the decimal part. Thus, `digits=(18, 15)` is required.

## Solution ✅

> Use `digits=(18, 15)` when defining high-precision geolocation fields.

```python
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    visit_latitude = fields.Float(string='Visit Latitude', digits=(18, 15))
    visit_longitude = fields.Float(string='Visit Longitude', digits=(18, 15))
```

## ⚠️ Pitfalls

- Using `digits=(15, 15)` will crash or fail to save longitudes like `120.12345` because it leaves 0 digits for the integer part (Total digits = 15, Decimal digits = 15). The first number in the tuple is the *total* number of digits, and the second is the *decimal* digits.
- To safely support `+/- 180.xxxxxxxxxxxxxxx`, the integer part needs up to 3 digits. 15 (decimal) + 3 (integer) = 18 total digits. So `(18, 15)` is correct.
