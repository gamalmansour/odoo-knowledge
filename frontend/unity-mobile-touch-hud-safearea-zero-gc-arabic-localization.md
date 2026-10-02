# Unity Mobile Touch HUD: Safe Area Adaptation, Zero-GC Arabic Localization & Unidirectional Input Authority

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | N/A (Unity Mobile Game Architecture)       |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `mobile-ui`, `touch-hud`, `safe-area`, `arabic-localization`, `zero-gc`, `input-authority`

---

## Problem

In complex mobile 3D action games (e.g. Genshin-style third-person action RPGs), implementing a mobile touch Head-Up Display (HUD) frequently suffers from three catastrophic failures:
1. **Safe Area Clipping & Touch Desynchronization:** Buttons clip behind hardware display cutouts (iPhone notch, dynamic island, home indicator bar, Android punch-holes), or become unpressable due to asymmetric corner radiuses when the device rotates $180^\circ$.
2. **Runtime Memory Leaks & Micro-Stutter (1% Low FPS Drops):** Dynamic string rendering and Arabic glyph reshaping inside `OnGUI()` or `Update()` allocate temporary heap strings every frame, triggering aggressive Garbage Collection (GC) pauses during fast-paced combat.
3. **Multi-Input Fragmentation:** Touch buttons directly manipulate character physics or combat state machines, bypassing the authoritative input manager and causing state desynchronization between desktop, gamepad, and touch controls.

```
GarbageCollector: GC_ALLOC overhead detected in Update()/OnGUI()
Memory leak in string concatenation for Arabic UI text labels.
Touch event bypassed PlayerInputManager causing state machine lock.
```

---

## Root Cause

1. Standard mobile UI components often rely on static screen coordinates (`Screen.width`, `Screen.height`) rather than dynamically querying `Screen.safeArea` and anchoring panels via normalized RectTransform anchors.
2. Arabic typography in Unity lacks native BiDi and glyph shaping in default uGUI Text components. Calling reshaping methods (e.g. `ArabicTextHelper.Shape(...)` or string interpolation `$"تبديل ({hero})"` each frame generates thousands of heap bytes every second.
3. Fragmented input architecture occurs when mobile touch button handlers call character controllers directly instead of firing virtual input triggers on the centralized input authority.

---

## Solution ✅

### 1. Unidirectional Input Authority Pipeline
Centralize all inputs through a single `PlayerInputManager`. Mobile touch HUD controls invoke virtual triggers that feed the exact same events and properties consumed by gameplay systems:

```csharp
// Mobile Touch HUD invokes:
PlayerInputManager.Instance.SetVirtualMove(analogVector);
PlayerInputManager.Instance.SetVirtualLook(lookDelta);
PlayerInputManager.Instance.TriggerVirtualAttack();
PlayerInputManager.Instance.TriggerVirtualJump();
PlayerInputManager.Instance.TriggerVirtualInteract();
```

### 2. Dynamic Safe Area Inset Management (`SafeAreaPanel.cs`)
Anchor UI containers dynamically to `Screen.safeArea` in normalized space, refreshing only when screen resolution or safe area dimensions change:

```csharp
public void ApplySafeArea()
{
    Rect safeArea = Screen.safeArea;
    Vector2Int screenSize = new Vector2Int(Screen.width, Screen.height);
    if (screenSize.x <= 0 || screenSize.y <= 0) return;

    Vector2 anchorMin = safeArea.position;
    Vector2 anchorMax = safeArea.position + safeArea.size;

    anchorMin.x /= screenSize.x;
    anchorMin.y /= screenSize.y;
    anchorMax.x /= screenSize.x;
    anchorMax.y /= screenSize.y;

    panelRectTransform.anchorMin = anchorMin;
    panelRectTransform.anchorMax = anchorMax;
}
```

### 3. Pre-Cached Zero-Allocation Arabic Typography
Pre-shape all static Arabic UI text strings during `Awake()` and store them in static readonly fields. Zero string allocations are generated in runtime render loops:

```csharp
private static string strAttack;
private static string strJump;

private static void PreCacheArabicStrings()
{
    strAttack = ArabicTextHelper.Shape("هجوم");
    strJump = ArabicTextHelper.Shape("قفز");
}
```

---

## ⚠️ Pitfalls

- **Finger ID Clumping:** In multi-touch games, do not track joystick dragging by touch index (`Input.GetTouch(0)`). Always track the specific `fingerId` that initiated the touch to prevent touch swaps when the second finger taps an action button.
- **Y-Axis Coordinate Inversion:** Unity GUI coordinates have $(0,0)$ at top-left with Y increasing downwards, whereas game movement forward is positive Y. Remember to invert Y when converting joystick displacement to movement vectors.
- **Button Occlusion of Combat Animations:** For characters with wide sweeping rotational attacks ($360^\circ$ spins), oversized buttons mask the weapon trail. Keep button opacity low at rest ($A \approx 0.40 - 0.45$) and pin clusters strictly to the outer perimeter.

---

## Verification

1. Run automated Python validation:
```bash
python3 validate_m64_touch_hud.py
```
2. Verify Unity Profiler records strictly `0 Bytes / Frame` GC allocation during active touch movement and combat.
3. Test physical rotation between LandscapeLeft and LandscapeRight on devices with camera cutouts (e.g. iPhone 13 Pro Max) to ensure zero element clipping.

---

## References

- Unity Screen.safeArea Documentation: https://docs.unity3d.com/ScriptReference/Screen-safeArea.html
- Related file: `backend/unity-physical-mobile-performance-benchmarking-and-device-truth.md`
