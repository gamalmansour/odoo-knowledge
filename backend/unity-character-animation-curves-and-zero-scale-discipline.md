# Unity Action-RPG Character Animation Curves, Zero-Scale Discipline, and Blendshape Synchronization

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `animation`, `anim`, `curves`, `blendshapes`, `zero-scale`, `mobile`, `action-rpg`

---

## Problem

When authoring or exporting character animation clips (`.anim`) for production action-RPGs in Unity:
1. Exporters frequently write redundant local scale curves (`m_LocalScale.x/y/z = 1.000`) for all skeleton bones across every clip. On mobile targets, these redundant curves bloat `.anim` file size and force unnecessary matrix multiplication overhead in the animation evaluation loop.
2. Blendshape animation curves often fail to evaluate or cause errors if bound to generic names instead of `blendShape.<ShapeName>` relative to the specific SkinnedMeshRenderer child path (e.g. `Visual/Body`).
3. Foot sliding and skating occur when locomotion clips lack grounded stance phase velocity synchronization.

## Root Cause

- Default Unity animation clip recording or external tool exporters serialize all 9 DOF (position, rotation, scale) for every bone transform in the hierarchy. For rigid organic skeletons, scale is constant ($1.0$), so scale curves represent $100\%$ wasteful memory allocation.
- Unity's `EditorCurveBinding` for SkinnedMesh blendshapes expects property names formatted as `blendShape.<BlendshapeName>` targeting the GameObject holding the `SkinnedMeshRenderer`.
- Stance feet drifting along $Y$ or translating during ground contact frames causes the CharacterController movement to mismatch the visible stride.

## Solution ✅

1. **Strip All Scale Curves (Zero-Scale Normalization):**
   Ensure all bone scales are omitted from animation curves. Only serialize rotation (`m_LocalRotation.x/y/z/w`) and translation where root/pelvis motion requires it:

```csharp
// In automated animation clip builders / post-processors
// Do NOT bind EditorCurveBinding.FloatCurve("", typeof(Transform), "m_LocalScale.x")
// Verify scale curve count equals exactly 0:
var bindings = AnimationUtility.GetCurveBindings(clip);
int scaleCurves = bindings.Count(b => b.propertyName.StartsWith("m_LocalScale"));
Assert.AreEqual(0, scaleCurves, "Scale curves must be stripped to prevent mobile memory bloat.");
```

2. **Standardize Blendshape Curve Bindings:**
   Target the deformable mesh path (`Visual/Body`) and use `blendShape.<ShapeName>`:

```csharp
EditorCurveBinding blendBinding = EditorCurveBinding.FloatCurve(
    "Visual/Body",
    typeof(SkinnedMeshRenderer),
    "blendShape.Face_Blink_L"
);
AnimationUtility.SetEditorCurve(clip, blendBinding, blinkCurve);
```

3. **Ground Stance Lock for Locomotion:**
   Pin stance feet at $Y = 0.000\text{m} \pm 0.001\text{m}$ during contact frames, and align animation stride speed with player locomotion parameters ($1.4\text{m/s}$ Walk, $4.2\text{m/s}$ Run, $6.8\text{m/s}$ Sprint).

## ⚠️ Pitfalls

- **macOS AppleDouble Files:** When scanning directory assets via Python `os.listdir()` on external SSDs or network mounts, filter out `not f.startswith(".")` to avoid counting invisible `._Ahmed_Idle.anim` files as clips.
- **Weapon Arc Dislocation:** Do not animate the weapon socket directly if it is parented under `RightHand`. Instead, keyframe `RightForeArm` and `RightHand` rotations so the rigid weapon tip forms a clean planar arc.
- **Eye Mesh Distortion:** Never bind facial blendshapes to eye mesh GameObjects (`Visual/Eyes`). Keep eyes rigidly bound to `Head` bone to preserve spherical geometry and prevent corneal clipping.

## Verification

```bash
python3 validate_ahmed_animations.py
# Check:
# - total_clips: 20
# - scale_curves: 0
# - nan_or_inf_count: 0
# - stance_y_delta: 0.000m
```

## References

- Related file: `backend/unity-action-rpg-locomotion-kinesthetics.md`
- Related file: `backend/unity-rigged-3d-character-models-and-ai-portraits.md`
- Deliverable: `/Docs/m6.3d-ahmed-animation-production-validation.md`
