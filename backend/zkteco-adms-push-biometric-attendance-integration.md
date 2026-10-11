# ZKTeco Native ADMS / IClock Push Protocol Direct Integration with Odoo Attendance

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-29                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `zkteco`, `biometric`, `adms`, `iclock`, `attendance`, `hr_attendance`, `iot`, `hardware`, `push-protocol`

---

## Problem

Companies purchasing ZKTeco biometric attendance machines (e.g., ZKTeco MB20 Face & Fingerprint terminals) are often told they must purchase third-party cloud middleware, paid Odoo App Store modules, or run brittle Windows desktop sync utilities (like ZKTimeNet or Att2008) on a dedicated local PC to bridge attendance data to Odoo.

Attempting to connect the device's native "Cloud Server / ADMS" setting directly to standard Odoo fails because Odoo lacks native HTTP routes for the ZKTeco ADMS / IClock protocol (`/iclock/cdata`, `/iclock/getrequest`), leading to:
- HTTP 404 on handshake requests (`GET /iclock/cdata?SN=...`).
- Terminal buffer overflow and stalled synchronization.
- Punch records trapped inside device memory.

## Root Cause

ZKTeco terminals equipped with ADMS firmware push attendance records proactively over HTTP/HTTPS using the proprietary IClock text protocol:
1. **Handshake (GET):** The machine calls `GET /iclock/cdata?SN=<SN>&options=all&pushver=...` expecting plain-text configuration strings (`GET OPTION FROM: <SN>\nStamp=0\n... Realtime=1\n`).
2. **Punch Ingestion (POST):** The machine sends `POST /iclock/cdata?SN=<SN>&table=ATTLOG` with raw tab-delimited punch lines:
   ```text
   <PIN>\t<YYYY-MM-DD HH:MM:SS>\t<VERIFY_TYPE>\t<PUNCH_STATE>\t<WORKCODE>\t<RESERVED>\t<RESERVED>
   ```
3. **Buffer Clearance:** The terminal expects the exact response `OK: <count>\n` where `<count>` matches the processed lines. If the server returns HTTP 500, HTML error pages, or missing count, the terminal will NOT clear its push buffer and will retry indefinitely, eventually halting all new transmissions.
4. **Timezone Discrepancy:** The terminal transmits naive local wall-clock time (e.g. `2026-09-29 09:00:00` in Egypt). Odoo ORM requires naive UTC.

## Solution ✅

Implement a lightweight, native Odoo HTTP controller and staging log model:

### 1. HTTP Controller (`controllers/main.py`)

Handle the handshake, heartbeat, and punch ingestion:

```python
from datetime import datetime
import pytz
from odoo import SUPERUSER_ID, fields, http
from odoo.http import Response, request

class ZktecoPushController(http.Controller):

    @http.route(['/iclock/cdata', '/cdata'], type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_cdata(self, **kwargs):
        env = request.env(user=SUPERUSER_ID)
        sn = kwargs.get('SN') or kwargs.get('sn')
        if not sn:
            return Response('ERROR: Missing SN\n', content_type='text/plain', status=400)

        device = self._get_or_create_device(env, sn)

        # 1. Handshake response
        if request.httprequest.method == 'GET':
            config_response = (
                f'GET OPTION FROM: {sn}\n'
                f'Stamp=0\n'
                f'ErrorDelay=30\n'
                f'Delay=10\n'
                f'Realtime=1\n'
                f'Encrypt=0\n'
            )
            return Response(config_response, content_type='text/plain')

        # 2. Punch Push (table=ATTLOG)
        raw_body = request.httprequest.data.decode('utf-8', errors='ignore')
        lines = [line.strip() for line in raw_body.splitlines() if line.strip()]
        processed_count = 0

        for line in lines:
            parts = line.split('\t') if '\t' in line else line.split()
            if len(parts) < 2:
                continue

            user_pin = parts[0].strip()
            local_time_str = parts[1].strip()
            
            # UTC normalization
            naive_local, utc_punch_dt = self._convert_to_utc(local_time_str, device.device_timezone)

            # Match employee and create staging log
            employee = env['hr.employee'].sudo().search([('biometric_id', '=', user_pin)], limit=1)
            log = env['zkteco.attendance.log'].sudo().create({
                'device_id': device.id,
                'user_pin': user_pin,
                'employee_id': employee.id if employee else False,
                'punch_time': utc_punch_dt,
                'raw_data': line,
                'state': 'processed' if employee else 'unmapped',
            })
            if employee and device.auto_create_attendance:
                log._process_to_attendance(employee)

            processed_count += 1

        return Response(f'OK: {processed_count}\n', content_type='text/plain')

    @http.route(['/iclock/getrequest', '/getrequest'], type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_getrequest(self, **kwargs):
        return Response('OK\n', content_type='text/plain')
```

### 2. Debounce & First-In / Last-Out Access Control Policy (`models/zkteco_attendance_log.py`)

When biometric terminals control electronic door locks, employees punch repeatedly (e.g. 5–10 times a day) simply to open doors. The **First-In / Last-Out** policy ensures:
- **First punch of the local day:** creates `hr.attendance` Check-In.
- **Subsequent door opening punches:** continuously update Check-Out of the same day's record (rather than splitting attendance into fragmented micro-sessions).
- **All individual punches:** remain preserved in `zkteco.attendance.log` for forensic audit.

```python
def _process_first_last_attendance(self, employee):
    Attendance = self.env['hr.attendance']
    device_tz = pytz.timezone(self.device_id.device_timezone or 'Africa/Cairo')

    # Identify local calendar day boundaries in UTC
    punch_utc = pytz.UTC.localize(self.punch_time) if self.punch_time.tzinfo is None else self.punch_time
    punch_local = punch_utc.astimezone(device_tz)
    local_date = punch_local.date()

    start_local = device_tz.localize(datetime.combine(local_date, datetime.min.time()))
    end_local = device_tz.localize(datetime.combine(local_date, datetime.max.time()))
    start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

    # Search for today's existing attendance
    day_att = Attendance.search([
        ('employee_id', '=', employee.id),
        ('check_in', '>=', start_utc),
        ('check_in', '<=', end_utc),
    ], order='check_in asc', limit=1)

    if not day_att:
        # First punch of the day: create Check-In
        new_att = Attendance.create({
            'employee_id': employee.id,
            'check_in': self.punch_time,
            'in_mode': 'biometric',
            'zk_device_id': self.device_id.id,
        })
        self.write({'state': 'processed', 'attendance_id': new_att.id})
    else:
        # Subsequent punch: update Check-Out with latest time
        if not day_att.check_out or self.punch_time >= day_att.check_out:
            day_att.write({'check_out': self.punch_time, 'out_mode': 'biometric'})
            self.write({'state': 'processed', 'attendance_id': day_att.id})
```

---

## ⚠️ Pitfalls

1. **Never Throw HTTP 500 to the Device:**
   If an employee PIN is missing from Odoo, do NOT raise an exception or fail the HTTP request. Always save the punch as `unmapped` in a staging log and return `OK: <count>\n`. If the device receives an error code, it locks up its push queue.
2. **Timezone Misalignment:**
   Hardware transmits local time without timezone offset. If you directly store the incoming string into Odoo's Datetime field, it will be offset by 2 or 3 hours (e.g., Cairo is UTC+2 / UTC+3 in summer). Always localize to device timezone, convert to UTC, and strip `tzinfo`.
3. **Odoo 19 Constraint Syntax:**
   In Odoo 19, `_sql_constraints = [...]` is deprecated and generates registry warnings. Use `models.Constraint('unique(...)', 'Error msg')`.
4. **Odoo 19 Search View RNG:**
   In Odoo 19 search views, `<group expand="0" string="Group By">` violates RelaxNG validation. `<group>` in search views should have no attributes.
5. **Nginx / Reverse Proxy Configuration:**
   If Odoo is behind Nginx, ensure `/iclock/` routes pass raw body without buffering timeouts and forward client IP (`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`).
6. **Selection Method Must Accept `self`:**
   When passing a callable to `fields.Selection(selection=func)`, Odoo's web client calls `fields_get()`, which runs `determine(selection, env[model])` passing `self` to the callable. A zero-argument function (`def _get_timezones():`) will cause `TypeError: takes 0 positional arguments but 1 was given` when loading views in the browser. Always accept `self`: `def _tz_get(self):`.
7. **Odoo 19 `hr.attendance` Open Session Constraint (`_check_validity`):**
   If an employee has an open attendance session (`check_out=False`) from an earlier date, calling `Attendance.create({'employee_id': ..., 'check_in': ...})` triggers `ValidationError`. Always defensively auto-close prior open attendances (`prior.write({'check_out': prior.check_in})`) before creating the new day's attendance record. See `backend/zkteco-offline-excel-usb-attendance-import.md` for batch handling.

---

## Verification

1. Simulate device handshake:
   ```bash
   curl -i "http://localhost:8020/iclock/cdata?SN=TEST123456&options=all"
   ```
   Should return HTTP 200 with `GET OPTION FROM: TEST123456`.

2. Simulate punch push:
   ```bash
   curl -i -X POST "http://localhost:8020/iclock/cdata?SN=TEST123456&table=ATTLOG" \
     -H "Content-Type: text/plain" \
     --data-binary $'101\t2026-09-29 09:00:00\t15\t0\t0\t0\t0\n'
   ```
   Should return `OK: 1`.

3. Verify that `hr.attendance` has a new record with `in_mode = 'biometric'` and proper UTC check-in.
