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

### 2. Debounce & Attendance State Machine (`models/zkteco_attendance_log.py`)

Prevent rapid double-punching from closing attendance immediately after check-in:

```python
def _process_to_attendance(self, employee):
    debounce_sec = self.device_id.debounce_seconds or 60
    threshold = self.punch_time - timedelta(seconds=debounce_sec)

    recent_punch = self.search([
        ('id', '!=', self.id),
        ('employee_id', '=', employee.id),
        ('punch_time', '>=', threshold),
        ('punch_time', '<=', self.punch_time),
        ('state', '=', 'processed'),
    ], limit=1)

    if recent_punch:
        self.write({'state': 'ignored', 'error_message': 'Debounce filtered'})
        return

    open_attendance = self.env['hr.attendance'].search([
        ('employee_id', '=', employee.id),
        ('check_out', '=', False),
    ], order='check_in desc', limit=1)

    if open_attendance:
        open_attendance.write({'check_out': self.punch_time, 'out_mode': 'biometric'})
        self.write({'state': 'processed', 'attendance_id': open_attendance.id})
    else:
        new_att = self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': self.punch_time,
            'in_mode': 'biometric',
            'zk_device_id': self.device_id.id,
        })
        self.write({'state': 'processed', 'attendance_id': new_att.id})
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
