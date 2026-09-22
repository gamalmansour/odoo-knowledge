# Unity Mobile CharacterController Spawn Trap, Input Overwrite, and 3rd-Person Camera Clipping

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | Unity 6 / URP / iOS / Android             |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `character-controller`, `camera-clipping`, `mobile-touch`, `spherecast`, `locomotion`

---

## Problem

On mobile builds, the player character appears completely frozen and unable to move forward/backward/left/right. Simultaneously, the third-person follow camera is clamped extremely close into the back of the player's head or inside the neck geometry (apparent "face clipping").

```
Symptoms:
1. CharacterController.Move() produces 0 velocity or stutters without translating.
2. ThirdPersonOrbitCamera distance snaps to minDistance (1.2m) regardless of defaultDistance (4.5m).
3. Mobile touch joystick inputs appear ignored or wiped out every frame.
4. Procedural animations (stride bobbing, lean, banking) never play.
```

---

## Root Cause

1. **Physical Collider Entrapment at Spawn:** The player's `CharacterController` was spawned at `villageCenter + Vector3.up * 0.1f` (`(0, 0.1, 0)`). However, the procedural terrain generator placed a solid stone well (`Village_Well`) with a `CapsuleCollider` (radius 1.6m, height 0.8m) and wooden arch posts directly at `(0, 0.4, 0)`. The character was spawned directly inside the well colliders, physically jamming the character controller.
2. **Obstacle Collision SphereCast Collapse:** The camera's `SphereCast` origin was computed at `target.position + targetOffset` without an offset along the backward vector. Starting inside or adjacent to the character and well geometry caused the `SphereCast` to immediately detect hits at $d \approx 0$, collapsing `currentDistance` down to `minDistance = 1.2f`. Furthermore, the `collisionLayers` mask did not exclude the `Player` layer.
3. **Desktop Input Overwriting Virtual Mobile Input:** In the unified input manager, `Update()` polled keyboard inputs. When running on mobile where `h == 0 && v == 0`, legacy code reassigned `MoveInput = Vector2.zero`, overwriting virtual joystick inputs.
4. **Procedural VisualRoot Lookup Race:** `ProceduralAnimatorController` searched for `visualRoot` in `Awake()`, but procedural character builder meshes were instantiated in `Start()`. Because `visualRoot` remained `null`, procedural stride and banking loops early-exited.

---

## Solution ✅

### 1. Relocate Spawn Position to Open Plaza
Spawn the player in an unobstructed plaza outside the well's collision footprint:
```csharp
player = SetupPlayer(villageCenter + new Vector3(0f, 0.1f, -5.5f));
```

### 2. Camera SphereCast Offset & Layer Masking
- Adapt default camera distance for portrait mobile aspect ratios (`defaultDistance = 5.5f`).
- Increase `minDistance` to $\ge 2.2\text{m}$ so it never clips into character geometry.
- Start `SphereCast` with a forward offset along `backDir` and mask out `Player` and `Ignore Raycast` layers:
```csharp
float startOffset = collisionRadius + 0.35f;
Vector3 rayOrigin = smoothedTargetPos + backDir * startOffset;
float castDistance = Mathf.Max(0.1f, effectiveDefaultDistance - startOffset);
int mask = collisionLayers & ~(1 << LayerMask.NameToLayer("Player")) & ~(1 << LayerMask.NameToLayer("Ignore Raycast"));

if (Physics.SphereCast(rayOrigin, collisionRadius, backDir, out RaycastHit hit, castDistance, mask, QueryTriggerInteraction.Ignore))
{
    float hitDist = hit.distance + startOffset;
    desiredDistance = Mathf.Clamp(hitDist - collisionRadius, minDistance, effectiveDefaultDistance);
}
```

### 3. Decouple Desktop & Virtual Inputs
Keep separate state variables for `desktopMove` and `virtualMove`. Only let desktop inputs override if their magnitude exceeds zero:
```csharp
MoveInput = desktopMove.sqrMagnitude > 0.001f ? desktopMove : virtualMove;
LookInput = desktopLook.sqrMagnitude > 0.001f ? desktopLook : virtualLook;
virtualLook = Vector2.zero; // Consume delta
IsSprinting = desktopSprint || virtualSprint;
```

### 4. Dynamic VisualRoot Resolution for Procedural Locomotion
Dynamically resolve `visualRoot` when skins are switched or after meshes finish building in `Start()`:
```csharp
public void ResolveVisualRoot()
{
    var wardrobe = GetComponent<CharacterWardrobeManager>();
    if (wardrobe != null)
    {
        var skinDef = wardrobe.GetActiveSkinDefinition();
        if (skinDef != null && skinDef.skinMeshRoot != null && skinDef.skinMeshRoot.activeSelf)
        {
            visualRoot = skinDef.skinMeshRoot.transform;
            initialVisualPos = visualRoot.localPosition;
            initialVisualRot = visualRoot.localRotation;
            return;
        }
    }
}
```

---

## ⚠️ Pitfalls

- **Two `controller.Move` Calls:** Never call `controller.Move` once for horizontal velocity and again for vertical gravity in the same frame. Combine them into a single `controller.Move((currentHorizontalVelocity + Vector3.up * verticalVelocity) * Time.deltaTime)` to avoid jitter and erratic `isGrounded` evaluation.
- **Narrow Portrait FOV:** In mobile portrait mode (9:20 aspect ratio), horizontal FOV shrinks drastically. A default distance of 4.0m looks like a first-person zoom; use 5.5m - 6.0m for natural third-person framing.
- **Immediate Setter Sync:** In `SetVirtualMove` / `SetVirtualSprint`, set `MoveInput` and `IsSprinting` immediately inside the setter method so that EditMode unit tests can test virtual input deterministically without needing a frame update.

---

## Verification

```bash
# 1. Run EditMode test suite
/Applications/Unity/Hub/Editor/6000.6.0f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -nographics -projectPath "Phoenix_Vertical_Slice" \
  -runTests -testPlatform EditMode -testResults "test_results.xml"

# 2. Capture screenshot on connected physical iPhone
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device capture screenshot \
  --device "<UDID>" --destination "screenshot.png"
```

---

## References

- Related: `misc/unity-arabic-rtl-bidi-shaping-mobile-ui.md`
- Related: `misc/unity-ios-device-il2cpp-compilation-and-codesign.md`
