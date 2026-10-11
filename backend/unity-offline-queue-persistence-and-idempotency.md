# Unity-to-Odoo Offline Queue Persistence and Idempotency Architecture

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `odoo19`, `rest-api`, `offline-persistence`, `idempotency`, `mobile`, `csharp`

---

## Problem

In mobile cross-platform games connecting to an Odoo backend:
1. **Data Loss on Force Quit:** Transient in-memory HTTP request queues (`Queue<T>`) lose all un-synced player progress, XP, and puzzle solutions when the operating system abruptly kills the application (memory pressure, low battery, user swipe-kill).
2. **Duplicate Awards (Retry Storms):** When mobile network connectivity drops right after the server processes a request but before the client receives the `200 OK`, the client's retry mechanism sends duplicate requests, awarding redundant XP or items.
3. **File Corruption from Partial Writes:** Directly overwriting JSON save files on disk during a power cut or crash causes partial bytes, resulting in unparseable JSON on the next startup.
4. **Dead-Letter Thundering Herd:** Permanent 4xx client errors repeatedly re-attempted indefinitely block subsequent queue items.

## Root Cause

1. Using volatile RAM queues instead of disk-backed atomic persistence.
2. Missing UUIDv4 `X-Idempotency-Key` headers on client requests and lack of server-side unique event deduplication before applying database mutations (`student.write({'xp': ...})`).
3. Using naive `File.WriteAllText()` directly on target files rather than atomic temporary file swaps (`.tmp` -> `File.Replace`).

## Solution ✅

### 1. Atomic Disk-Backed Queue with SHA-256 Validation (`FileBackedOfflineQueue.cs`)
Write to a `.tmp` file and perform an atomic filesystem replacement. Maintain SHA-256 integrity hashes and quarantine corrupt files to `.bak` backups:

```csharp
string tempPath = queueFilePath + ".tmp";
File.WriteAllText(tempPath, json);

if (File.Exists(queueFilePath))
{
    File.Replace(tempPath, queueFilePath, null);
}
else
{
    File.Move(tempPath, queueFilePath);
}
```

### 2. Client-Side Idempotency Header and Exponential Backoff
Every enqueued payload generates an immutable UUIDv4 idempotency key passed via `X-Idempotency-Key`:

```csharp
req.SetRequestHeader("X-Idempotency-Key", entry.idempotencyKey);
```

Exponential backoff with $\pm 15\%$ jitter:
$$T = \min(300, 2.0 \times 2^{n-1}) \pm \text{jitter}$$

Permanent 4xx errors are immediately isolated in `dead_letter_queue.json` to prevent queue head-of-line blocking.

### 3. Server-Side Deduplication in Odoo 19 Controller (`main.py`)
Check the idempotency key against indexed `phoenix.event.uuid` before crediting student progression:

```python
idempotency_key = request.httprequest.headers.get("X-Idempotency-Key") or body.get("idempotency_key")
if idempotency_key:
    existing = request.env["phoenix.event"].sudo().search([("uuid", "=", idempotency_key)], limit=1)
    if existing:
        return _json({
            "ok": True,
            "duplicate": True,
            "puzzle_id": puzzle_id,
            "xp_awarded": 0,
            "student": _student_payload(student),
        })

# Safe to award XP and record event
student.sudo().write({"xp": student.xp + xp_earned})
request.env["phoenix.event"].sudo().create({
    "uuid": idempotency_key or str(uuid.uuid4()),
    "student_id": student.id,
    "name": "puzzle_solved",
    "payload": json.dumps({"puzzle_id": puzzle_id, "xp_earned": xp_earned}),
})
```

## ⚠️ Pitfalls

- **Do Not Rely on `Application.quitting`:** Mobile OSs rarely call `OnApplicationQuit()` when force-killed; flush the queue immediately to disk on `Enqueue()` rather than deferring to exit hooks.
- **Dead-Letter Isolation:** Always distinguish retryable network errors (timeout, 502, 503) from fatal client validation errors (400, 401, 403, 404). Fatal errors must never loop indefinitely.
- **Queue Cap:** Always enforce a hard ceiling (e.g. 200 items) to prevent unbounded storage growth during prolonged offline periods.

## Verification

Run automated persistence tests via Unity batchmode:
```bash
/Applications/Unity/Hub/Editor/6000.6.0f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -nographics -projectPath "Phoenix_Vertical_Slice" \
  -runTests -testPlatform EditMode -testFilter OfflinePersistenceTests
```
