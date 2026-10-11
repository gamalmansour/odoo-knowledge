# Unity-Odoo REST API Auth Contract & TimeScale Freeze Prevention

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `rest-api`, `authentication`, `timescale`, `mobile`, `bullet-time`, `odoo19`

---

## Problem

When integrating a Unity 3D client with an Odoo 19 backend REST API for real-time player telemetry and XP synchronization:
1. Student authentication calls fail with HTTP 400 or default to offline fallback because the client sends `handle` while the backend controller inspects `body.get("username")`.
2. When the game enters Bullet Time or Hit Stop (`Time.timeScale = 0.25f` or `0.05f`), if an enemy or the player dies or scene changes mid-routine, the coroutine aborts and `Time.timeScale` remains permanently slowed down, rendering the game unplayable.

```
[Meen Ysed Cloud] Server offline or unreachable. Entering local student mode.
```

## Root Cause

1. **Parameter Discrepancy:** Odoo JSON controllers extracting user credentials from request payloads often check `username` for login verification while external game engines use player handles (`handle`). Additionally, saved tokens in `PlayerPrefs` bypass session logs if not explicitly handled in `Awake()`.
2. **TimeScale State Leaks:** In Unity, `Time.timeScale` is a global static property not reset by scene loads or object destruction. A coroutine interrupted by `GameObject.Destroy()` leaves `Time.timeScale` locked at the sub-normal value.

## Solution ✅

### 1. Dual-Key Payload in UnityWebRequest
Always send both `username` and `handle` in the authentication JSON payload:

```csharp
string jsonBody = $"{{\"username\":\"{handle}\",\"handle\":\"{handle}\",\"pin\":\"{pin}\"}}";
```

### 2. Session Restoration & Profile Refresh
In `Awake()`, check for cached tokens and restore user identity:
```csharp
authToken = PlayerPrefs.GetString("MeenYsed_AuthToken", "");
studentName = PlayerPrefs.GetString("MeenYsed_StudentName", "أحمد");
if (!string.IsNullOrEmpty(authToken))
{
    isLoggedIn = true;
    Debug.Log($"<color=green>[Meen Ysed Cloud] Logged in as: {studentName} (Session Restored)</color>");
}
```

### 3. Defensive TimeScale Restoration
In any manager handling Hit Stop or Bullet Time (`CombatFeedbackManager`), implement `OnDisable()` and `OnDestroy()` safety nets:

```csharp
private void OnDisable()
{
    Time.timeScale = 1.0f;
}

private void OnDestroy()
{
    Time.timeScale = 1.0f;
}
```

## ⚠️ Pitfalls

- Never rely solely on `WaitForSecondsRealtime()` without an `OnDisable` cleanup; scene unloads will freeze the engine time permanently.
- Odoo 19 API endpoints require `type='json'` with `application/json` Content-Type headers, else Odoo returns 400 Bad Request.

## Verification

Run the automated E2E test suite:
```bash
python3 test_e2e_meenysed.py
```
Output confirms:
```
✅ PASS [3.5 Cloud Sync & Auth] MeenYsedApiClient successfully authenticated with live Odoo 19
✅ PASS [4.8 Live 3D Sync] Synced 3D progress to Odoo: +25 XP awarded
```
