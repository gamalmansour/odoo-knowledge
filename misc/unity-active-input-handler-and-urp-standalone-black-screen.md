# Unity Standalone Black Screen: activeInputHandler Exception Loop, Stripped Shaders & URP Registration

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All (Unity 6 / Unity 2022+ Hybrid Projects) |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `unity6`, `standalone`, `macos`, `black-screen`, `activeInputHandler`, `inputsystem`, `urp`, `shaders`, `blitter`

---

## Problem

When launching a Unity 6 standalone build (e.g. macOS `.app` or Windows `.exe`), the game window opens to a persistent **Black Screen** without rendering the 3D world, terrain, or characters. The app may appear frozen or consume heavy disk I/O, and `Player.log` balloons rapidly into hundreds of megabytes (e.g. 300+ MB) with infinite repeated exceptions:

```
InvalidOperationException: You are trying to read Input using the UnityEngine.Input class, but you have switched active Input handling to Input System package in Player Settings.
  at UnityEngine.Input.GetKey (UnityEngine.KeyCode key)
  at MeenYsed.Player.PlayerInputManager.HandleDesktopInputs ()
  at MeenYsed.Player.PlayerInputManager.Update ()
```

Additionally, graphics log output may show:
```
Exception: Blitter is already initialized. Please only initialize the blitter once or you will leak engine resources.
```

## Root Cause

1. **Active Input Handler Mismatch**:
   In Unity 6, adding `com.unity.inputsystem` sets `activeInputHandler: 1` (New Input System Only) in `ProjectSettings/ProjectSettings.asset`. If scripts still query legacy `UnityEngine.Input.GetKey(...)` or `Input.GetAxis(...)` in `Update()`, the native engine throws an `InvalidOperationException` 60 times per second. Writing hundreds of megabytes of stack traces synchronously freezes the main render loop on frame 0, leaving a black void.

2. **URP Render Pipeline Unregistered in GraphicsSettings**:
   In `ProjectSettings/GraphicsSettings.asset`, `m_CustomRenderPipeline: {fileID: 0}` left the engine starting up in legacy Built-in mode, while scenes and camera components (`UniversalAdditionalCameraData`) expected URP. This triggers pipeline initialization conflicts (`Blitter is already initialized`).

3. **Runtime Stripping of Shaders**:
   Shaders referenced only via `Shader.Find(...)` in procedural code (such as custom cel shaders) are stripped during standalone build packaging unless assigned to `m_AlwaysIncludedShaders` in `GraphicsSettings.asset`. Calling `new Material(Shader.Find("..."))` returns `null`, resulting in `ArgumentNullException` during character generation.

4. **Camera SphereCast Self-Collision**:
   Third-person orbit cameras casting a `SphereCast` from the player's head against `~0` (all layers) immediately hit the player's own `CharacterController` or mesh colliders, collapsing `desiredDistance` to `minDistance` or inside the player model.

## Solution ✅

### 1. Enable Both Input Handlers in `ProjectSettings.asset`
Set `activeInputHandler: 2` (0 = Legacy, 1 = New, 2 = Both):
```yaml
  activeInputHandler: 2
```

### 2. Implement Resilient Hybrid Input Handling
In input management scripts, query `UnityEngine.InputSystem.Keyboard.current` and `Mouse.current` first, and wrap legacy `UnityEngine.Input` in safe exception guards:
```csharp
#if ENABLE_INPUT_SYSTEM
var kb = Keyboard.current;
if (kb != null)
{
    if (kb.wKey.isPressed) v += 1f;
    ...
    return;
}
#endif

// Legacy fallback
try
{
    if (Input.GetKey(KeyCode.W)) v += 1f;
}
catch (System.Exception) {}
```

### 3. Register URP Asset & Always Included Shaders in `GraphicsSettings.asset`
```yaml
  m_AlwaysIncludedShaders:
  - {fileID: 4800000, guid: <YOUR_CEL_SHADER_GUID>, type: 3}
  ...
  m_CustomRenderPipeline: {fileID: 11400000, guid: <YOUR_URP_ASSET_GUID>, type: 2}
```

### 4. Guard Camera SphereCast from Self-Collision
In `ThirdPersonOrbitCamera.cs`:
```csharp
if (Physics.SphereCast(smoothedTargetPos, collisionRadius, backDir, out RaycastHit hit, defaultDistance, collisionLayers, QueryTriggerInteraction.Ignore))
{
    if (target == null || (hit.transform != target && !hit.transform.IsChildOf(target)))
    {
        desiredDistance = Mathf.Clamp(hit.distance - collisionRadius, minDistance, defaultDistance);
    }
}
```

## ⚠️ Pitfalls

- Never rely on `Shader.Find(...)` at runtime in standalone builds without adding the shader to `Always Included Shaders` or packing it into `Resources/`.
- Never leave `activeInputHandler: 1` if any legacy asset store package or utility queries `UnityEngine.Input`.
- Always verify `Player.log` size after launching; a runaway log file (>10 MB in <5s) immediately indicates an unhandled exception loop in `Update()`.

## Verification

Run the standalone executable and inspect `Player.log`:
```bash
cat ~/Library/Logs/<CompanyName>/<ProductName>/Player.log
```
The log must stay under 10 KB, showing clean initialization:
```
[Meen Ysed] Vertical Slice Bootstrapped Successfully! 60 FPS Target Ready.
```

## References

- Related: `odoo-knowledge/misc/unity-il2cpp-path-spaces-and-mono-standalone.md`
