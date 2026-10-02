# Unity Mecanim Humanoid Avatar Mapping, Facial Mask Isolation, and In-Place Root Motion

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `mecanim`, `avatar`, `humanoid`, `animator-controller`, `blend-tree`, `avatar-mask`, `facial-animation`

---

## Problem

When setting up anime action-RPG characters in Unity Mecanim:
1. Custom skeleton hierarchies with secondary cloth/hair bones (e.g. 63-bone rigs) can fail Humanoid avatar validation if secondary bones are mistakenly mapped to humanoid slots, or if required humanoid slots are missing.
2. Driving facial blendshapes through the Animator Controller often overrides or fights with body bone animations if layers aren't properly isolated.
3. Enabling `Apply Root Motion` on in-place locomotion clips causes characters to drift or slide unpredictably against the Unity `CharacterController`.

## Root Cause

- Unity's Humanoid Avatar requires a deterministic mapping of standard bones (Hips, Spine, Chest, Neck, Head, Clavicles, Limbs, Toes, and Fingers). Non-humanoid bones (scarf, hair, prop sockets) must remain unmapped in the `HumanDescription` to avoid joint twisting or retargeting errors.
- Without an `AvatarMask` configured to isolate body bones, a secondary Animator layer (like `Face`) with Weight = 1.0 overrides all lower-layer bone transforms with default or neutral transforms.
- When character velocity is governed by a script (`CharacterController.Move()`), setting `m_ApplyRootMotion: 1` causes double-accumulation of velocity or fighting between physics and animation.

## Solution ✅

1. **Map Only True Humanoid Bones in Avatar:**
   Map core skeletal bones and finger phalanxes (51-54 bones), leaving secondary cloth, hair, weapon, and scabbard bones unmapped:

```csharp
HumanBone[] humanBones = new HumanBone[] {
    new HumanBone { boneName = "Pelvis", humanName = "Hips" },
    new HumanBone { boneName = "Spine", humanName = "Spine" },
    new HumanBone { boneName = "Chest", humanName = "Chest" },
    new HumanBone { boneName = "Neck", humanName = "Neck" },
    new HumanBone { boneName = "Head", humanName = "Head" },
    // Arms, Legs, Feet, Toes, and 30 finger bones...
};
// Exclude: Scarf1..4, Hair1..3, Weapon, Sheath, Root
```

2. **Isolate Facial Layer with AvatarMask:**
   Create an `AvatarMask` asset with all humanoid body parts disabled ($0$), and only the deformable mesh GameObject (`Visual/Body`) enabled ($1$). Assign this mask to the `Face` layer:

```yaml
AvatarMask:
  m_Mask: 00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
  m_Elements:
  - m_Path: 
    m_Weight: 0
  - m_Path: Visual/Body
    m_Weight: 1
```

3. **Strictly Disable Root Motion for In-Place Animation:**
   Ensure the Animator component has `m_ApplyRootMotion: 0`.

## ⚠️ Pitfalls

- **Verbal Specification Inversions:** Always cross-reference clip curves (rotational axes and durations) against the master character design spec before wiring transitions, avoiding reliance on casual summary glosses.
- **Any State Stutter:** Restrict `Any State` transitions strictly to interruptive emergency reactions (`Hit`, `Death`) with clear exit times to avoid infinite loop stutter.

## Verification

```bash
python3 validate_ahmed_mecanim.py
# Check:
# - Avatar exists and is Humanoid
# - Required humanoid mappings valid
# - Controller assigned and Root Motion == OFF
# - Locomotion 1D Blend Tree [0.0, 1.4, 4.2, 6.8]
# - 42/42 checks passed
```

## References

- Related file: `backend/unity-character-animation-curves-and-zero-scale-discipline.md`
- Related file: `backend/unity-action-rpg-locomotion-kinesthetics.md`
- Deliverable: `/Docs/m6.3e-ahmed-mecanim-avatar-controller.md`
