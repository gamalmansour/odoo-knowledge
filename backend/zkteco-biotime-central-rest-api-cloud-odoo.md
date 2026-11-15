# Cloud Odoo.sh Biometric Attendance Sync via Central ZKTeco BioTime REST API vs Direct TCP 4370

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-11-15                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `zkteco`, `biotime`, `hr_attendance`, `odoo.sh`, `biometric`, `port-4370`

---

## Problem

> Legacy ZKTeco Odoo modules (`hr_zk_integration`) connect directly from Odoo to each physical fingerprint/face terminal over LAN TCP/UDP Port `4370` using `pyzk` (`ZK(ip, port=4370)`).
> When Odoo is hosted in the cloud (`Odoo.sh` / SaaS) and employees move across multiple construction sites (e.g., Riyadh, Jubail, Dammam) already connected to a central **ZKTeco BioTime** server, direct Port `4370` polling fails with network timeouts, requires unsafe firewall port-forwarding on every site router, and breaks when an employee punches IN on Site A and OUT on Site B.

```
UserError: Unable to connect, please check the parameters and network connections.
```

## Root Cause

1. Physical ZKTeco terminals sit behind private site NAT/4G routers unreachable from `Odoo.sh` over raw TCP/UDP `4370`.
2. Even if exposed, polling 10+ site terminals sequentially inside an Odoo cron risks worker timeouts (`CPU/Real time limit exceeded`), and single-device polling misses cross-site check-in/check-out pairing.
3. ZKTeco **BioTime 8.x / 9.x** already aggregates all remote terminals via ADMS/iClock push into a central HTTP/HTTPS server exposing `/jwt-api-token-auth/` and `/iclock/api/transactions/`.

## Solution ✅

Add a dual-mode `connection_type` (`tcp` vs `biotime_api`) on `zk.machine` using Python standard library `urllib.request`:

1. **Authenticate via JWT (`/jwt-api-token-auth/`)** or accept a long-lived API Token (`JWT <token>` / `Token <token>`).
2. **Fetch paginated cross-site transactions** from `/iclock/api/transactions/?page_size=200&start_time=<last_sync - 10m>` (the 10-minute overlap window protects against delayed 4G terminal uploads while deduplication prevents double-inserts).
3. **Match employees across devices** by checking `('device_id', 'emp_code', 'employee_number', 'pin', 'barcode')` dynamically.
4. **Commit per device in `ir.cron`** using `with self.env.cr.savepoint():` and `IrCron._commit_progress(1)` so one offline terminal never blocks the rest.

```python
auth_url = f"{base}/jwt-api-token-auth/"
tx_url = f"{base}/iclock/api/transactions/?{urllib.parse.urlencode(params)}"
# Convert terminal local timestamp (e.g. Asia/Riyadh) to naive UTC for Odoo Datetime fields:
local_dt = datetime.datetime.strptime(punch_str[:19], '%Y-%m-%d %H:%M:%S')
utc_dt = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
```

## ⚠️ Pitfalls

- **Timezone Offset Trap:** BioTime `/iclock/api/transactions/` returns `punch_time` in the server's local timezone (e.g., `Asia/Riyadh` UTC+3), whereas Odoo `fields.Datetime` expects naive UTC. Never hardcode `timedelta(hours=-2)`; always convert via `pytz.timezone(self.env.user.tz or 'Asia/Riyadh')`.
- **Delayed Site Syncs:** Construction site terminals on 4G routers may push punches to BioTime several minutes late. Always overlap `biotime_last_sync` by `-10 minutes` and deduplicate on `(employee_id, check_in, punch_type / machine_ip)`.
- **Preserve TCP Fallback:** Keep `connection_type = 'tcp'` as the default fallback so on-premise installations with direct LAN devices continue working without breaking changes.

## Verification

```python
# Unit test with mocked _biotime_get verifying idempotent import & UTC conversion:
machine.download_attendance()
machine.download_attendance()  # second call must create 0 duplicates
```

## References

- Related file: `upgrade/odoo19-hr-version-payroll-contract-lifecycle.md`
