# Unity Facial Blendshapes & Rigid Eye Isolation Architecture

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All (Game Engine / Pipeline)               |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `character-art`, `facial-rig`, `blendshapes`, `deformation`, `eye-isolation`

---

## Problem

When authoring facial blendshapes on stylized 3D anime character models with embedded eye globes (separate eyeball meshes), two major defects frequently emerge:
1. **Corneal Flattening / Eye Distortion:** Directly deforming the eyeball mesh with blink blendshapes causes unnatural pupil squashing, sclera clipping, and specular highlight distortion.
2. **Eyelid Arc Penetration:** Linear vertical morph targets for eyelids pierce the spherical corneal apex, creating black shading artifacts and intersecting the eye globe.

## Root Cause

- Eyeballs are spherical/ellipsoid hard structures that do not compress during physiological blinking; only surrounding palpebral tissue moves.
- Standard linear vertex interpolation in blendshapes moves vertices along straight chords rather than following the spherical curvature of the eyeball.

## Solution ✅

1. **Strict Mesh Separation & Rigid Eye Binding:**
   - Keep eyeball meshes (`Visual/Eyes`) 100% rigidly bound to the `Head` bone with zero blendshapes.
   - Author all facial deformation (blinks, smiles, jaw drops, brow movements) exclusively on the primary face/body mesh (`Visual/Body`).
2. **Parabolic Corneal Arc Trajectories:**
   - In blink blendshapes (`Face_Blink_L`, `Face_Blink_R`), project eyelid vertices forward along $+Z$ as they drop along $-Y$:
     $$\Delta Z = +0.004\text{m}, \quad \Delta Y = -0.018\text{m}$$
   - This wraps eyelid loops over the curved cornea with guaranteed clearance, completely eliminating clipping.
3. **ModelImporter Configuration:**
   - Ensure the `.meta` file of the face mesh has `importBlendShapes: 1` enabled:
     ```yaml
     meshes:
       importBlendShapes: 1
     ```
   - Register zeroed float weights in the target `SkinnedMeshRenderer.m_BlendShapeWeights` array.

## ⚠️ Pitfalls

- **Micro Bone Explosion:** Avoid adding dozens of micro facial bones (jaw, lips, cheeks, eye bones) unless proven necessary; this balloons mobile CPU vertex skinning and matrix transformation overhead.
- **Additive Compounding:** Always stress-test compound expressions (e.g. smile + wide open mouth) to ensure combined displacements do not produce self-intersecting geometry or inverted normals.

## Verification

Run automated validation checking that eyeball vertices have zero delta displacement and that compound blendshape deltas remain within sanity bounds:
```bash
python3 validate_ahmed_facial.py
```

## References

- Milestone M6.3-C: Ahmed Facial Rig & Blendshape Validation Specification (`Docs/m6.3c-ahmed-facial-rig-blendshape-validation.md`)
