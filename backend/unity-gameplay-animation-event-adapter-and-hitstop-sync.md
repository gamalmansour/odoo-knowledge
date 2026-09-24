# Unity Gameplay Animation Event Adapter, Zero-Allocation Hashes, and Hit-Stop Synchronization

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `animation`, `gameplay-integration`, `mecanim`, `hit-stop`, `event-adapter`, `csharp`, `mobile`

---

## Problem

When connecting character animation (Mecanim) to active action-RPG gameplay systems:
1. **Coupling & String Allocations:** Directly calling `animator.SetTrigger($"Attack_{step}")` or string parameters inside physics movement and combat code causes garbage-collected heap allocations every frame, and produces missing parameter warnings if names differ.
2. **Hit-Stop Desynchronization:** If the Animator's update mode is set to `UnscaledTime`, the animation keeps playing during combat hit-stop (`Time.timeScale = 0.05`), breaking the freeze-frame impact feel.
3. **Double Movement:** Enabling `Apply Root Motion` on characters driven by `CharacterController.Move()` causes physics and animation to fight or slide uncontrollably.

---

## Root Cause

- String-based Animator methods (`SetFloat("Speed", ...)`, `SetTrigger(...)`) incur internal hash lookups and string allocation overhead on every call.
- Direct parameter polling in `Update()` without change-detection thresholds repeatedly marks Animator state as dirty, causing unnecessary recalculations on mobile GPUs.
- Failing to synchronize `Animator.updateMode` with the game's timescale control results in visual desynchronization during hit-stop or bullet-time events.

---

## Solution ✅

### 1. Dedicated Decoupled Animation Adapter
Use a dedicated `AhmedAnimationAdapter` MonoBehaviour that consumes C# gameplay events (`OnDashTriggered`, `OnComboStep`, `OnJumpPressed`) and state properties (`CurrentSpeed`, `IsGrounded`, `IsGliding`):

```csharp
// Authority Direction: GAMEPLAY -> ANIMATION PARAMETERS -> MECANIM -> VISUAL
public class AhmedAnimationAdapter : MonoBehaviour
{
    private static readonly int SpeedHash = Animator.StringToHash("Speed");
    private static readonly int GroundedHash = Animator.StringToHash("Grounded");
    private static readonly int IsGlidingHash = Animator.StringToHash("IsGliding");
    private static readonly int JumpHash = Animator.StringToHash("Jump");
    private static readonly int DashHash = Animator.StringToHash("Dash");
    private static readonly int AttackHash = Animator.StringToHash("Attack");
    private static readonly int AttackIndexHash = Animator.StringToHash("AttackIndex");

    private float lastSpeed = -1f;

    private void UpdateLocomotionParameters()
    {
        float currentSpeed = playerController.CurrentSpeed;
        if (Mathf.Abs(currentSpeed - lastSpeed) > 0.02f)
        {
            animator.SetFloat(SpeedHash, currentSpeed, 0.08f, Time.deltaTime);
            lastSpeed = currentSpeed;
        }
    }
}
```

### 2. Hit-Stop Synchronization
Ensure the Animator component is configured with `AnimatorUpdateMode.Normal`:
```yaml
Animator:
  m_UpdateMode: 0 # Normal (follows Time.timeScale)
  m_ApplyRootMotion: 0 # Root motion strictly OFF
```
When `CombatFeedbackManager.Instance.TriggerHitStop(0.06f)` sets `Time.timeScale = 0.05f`, the Animator naturally slows down to a near-freeze, creating the visceral impact feel without desynchronizing from combat routines.

### 3. Strict Facial Value Clamping
Clamp all facial blendshape float inputs strictly between $0.0$ and $1.0$:
```csharp
animator.SetFloat(FaceSmileHash, Mathf.Clamp01(currentSmile));
animator.SetFloat(FaceMouthOpenHash, Mathf.Clamp01(currentMouthOpen));
```

### 4. Sprint Speed Mismatch & Foot-Drift Tolerance Policy
When gameplay sprint velocity (e.g. $8.0\text{ m/s}$) exceeds authored animation translation (e.g. $6.8\text{ m/s}$):
- **Never modify gameplay speed automatically:** Traversal pacing, jump reach, and combat spacing are carefully tuned to gameplay speeds.
- **Avoid high-frequency animation multiplier:** Scaling playback speed by $1.176\times$ causes unnatural leg fluttering in stylized anime characters.
- **Rely on Damping, Lean & Visual Masking:** Forward torso pitch ($12.5^\circ$), banking tilt ($14^\circ$), and dynamic camera pushback naturally mask the stance drift. Ensure stance drift remains strictly under the documented tolerance ($\le 0.030\text{m}$).

### 5. Mandatory Attack 02 $360^\circ$ Horizontal Cleave Preservation
Ensure spinning area-of-effect attacks (Attack 2) maintain a planar horizontal arc with root heel pivot. Avoid drifting into vertical diagonal slashes during combat tuning to maintain distinct visual silhouette from Attack 1.

---

## ⚠️ Pitfalls

- **Duplicate Subscriptions:** Always unsubscribe from C# gameplay events in `OnDisable()` or before re-subscribing in `OnEnable()` to avoid multi-triggering attacks or jumps.
- **Root Motion Leak:** Never set `m_ApplyRootMotion: 1` when using `CharacterController`. The CharacterController must remain the sole kinematic authority.
- **Desynchronizing Hit-Stop:** Never use `AnimatorUpdateMode.UnscaledTime` for combat characters; it completely breaks hit-stop freeze frames.
- **Art Rig Modification During Polish:** Keep skeleton (63 bones), meshes, blendshapes, materials, and shaders strictly frozen during gameplay polish gates.

---

## Verification

```bash
python3 validate_ahmed_gameplay_animation_polish.py
# Verify:
# - Foot contact stance drift <= 0.030m
# - Attack 2 is canonical 360-degree horizontal cleave
# - Hit-stop couples Time.timeScale = 0.05 to Animator
# - Ledge mantling state verified in PlayerClimbingSystem
# - 36/36 checks passed
```

---

## References

- Related file: `backend/unity-action-rpg-locomotion-kinesthetics.md`
- Related file: `backend/unity-mecanim-avatar-mapping-and-facial-mask-isolation.md`
- Deliverable: `/Docs/m6.3f1-ahmed-gameplay-animation-integration.md`
- Deliverable: `/Docs/m6.3f2-ahmed-gameplay-animation-polish.md`
