# GPS Geofence Check-in Falsely Rejects Reps Standing at the Customer

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-07-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `geolocation`, `gps`, `geofence`, `portal`, `javascript`, `field-sales`, `haversine`

---

## Problem

> Field reps constantly complain that a GPS geofence check ("you must be within X meters of the customer to start the visit") rejects them even though they are physically standing at the customer's door. Management suspects the reps are lying; reps insist the system is broken. Both are wrong — the code is.

## Root Cause

Three compounding issues, all common in naive geofence implementations:

1. **`getCurrentPosition` returns the FIRST fix, not a good one.** With `enableHighAccuracy: true` + a short timeout, the browser hands over the first available position — on mobile this is frequently a WiFi/cell-tower fix with an error radius of 100–2000 m. The rep's phone reports a point hundreds of meters away from where they stand.

2. **`pos.coords.accuracy` is ignored.** The Geolocation API tells you the error radius of every fix. Comparing `distance > allowed` without accounting for accuracy means a 50 m geofence is consumed entirely by device error before the rep moves a single step.

3. **`if partner.lat or partner.lng:` guard bug.** If only ONE coordinate is set on the customer (data-entry slip), the distance is computed against latitude/longitude 0 (the equator / prime meridian) → thousands of km → permanent rejection for that customer.

## Solution ✅

**Frontend — collect fixes, keep the best, send accuracy along:**

```javascript
// watchPosition for up to 20s, keep the most accurate fix,
// stop early once accuracy <= 20m, submit accuracy with the coords
watchId = navigator.geolocation.watchPosition(function (pos) {
    if (best === null || best.acc > pos.coords.accuracy) {
        best = {lat: pos.coords.latitude, lng: pos.coords.longitude, acc: pos.coords.accuracy};
    }
    if (TARGET_ACCURACY_M >= best.acc) { finish(); }
}, onErr, {enableHighAccuracy: true, maximumAge: 0});
setTimeout(finish, MAX_WAIT_MS);
```

**Backend — accuracy-aware comparison (reject only when the whole error circle is outside):**

```python
GPS_ACCURACY_MARGIN_CAP = 100.0    # cap so a weak fix can't stretch the fence
GPS_MAX_USABLE_ACCURACY = 200.0    # coarser than this => ask to retry, not "too far"

if accuracy > GPS_MAX_USABLE_ACCURACY:
    return 'gps_weak'              # tell the user to move to open sky and retry
effective_allowed = allowed + min(accuracy, GPS_ACCURACY_MARGIN_CAP)
if distance > effective_allowed:
    return 'too_far'
```

**Settle the argument — record the evidence:** store `check_in_distance` and `check_in_accuracy` on the record, and on every rejection post a chatter note with the computed distance, the accuracy, and Google Maps links for both points (`https://www.google.com/maps?q=lat,lng`). Disputes end when the numbers are visible.

**Guard the customer data:** enforce both coordinates set together with an `@api.constrains`, and only run the geofence when `partner.lat and partner.lng` (not `or`).

Reference implementation: `sale_visit` module (`models/sale_visit.py::_evaluate_gps_check`, `controllers/portal.py::portal_visit_start`, GPS script in `views/portal_templates.xml`).

## ⚠️ Pitfalls

- Raising the allowed-distance setting to silence complaints (e.g. 50 → 300 m) destroys the control: genuinely-absent reps pass. Fix the measurement, not the threshold.
- Inline `<script>` inside QWeb XML: `<` and `&` (including `&&`) break XML parsing. Write comparisons as `b > a` instead of `a < b` and use nested `if`/`||` instead of `&&`.
- `watchPosition`'s `timeout` option applies per-fix, not overall — manage the total wait with your own `setTimeout(finish, MAX_WAIT_MS)`.
- Don't trust `accuracy` blindly server-side: cap the margin it can add, otherwise a spoofed weak fix bypasses the fence.
- `float(kw.get('x') or 0) or None` silently turns 0 into None — acceptable for lat/lng (0,0 is in the ocean) but be aware of the pattern.
