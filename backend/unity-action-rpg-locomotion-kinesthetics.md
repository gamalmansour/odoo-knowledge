# Unity Action RPG Locomotion Kinesthetics & Fluid Movement Architecture

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `movement`, `kinesthetics`, `locomotion`, `inertia`, `banking`, `squash-stretch`, `genshin`

---

## Problem

In Action RPG games (like Genshin Impact or Zelda BotW), procedural movement often feels "stiff, robotic, and clunky" when relying on raw character controller translation:
1. **Instant Stop (Wall Effect):** Releasing movement keys causes the character to halt in a single frame with zero deceleration, breaking the illusion of physical weight.
2. **Upright Cylinder Syndrome:** Turning left or right while sprinting keeps the character model strictly vertical without banking or leaning into turns.
3. **Hard Landing Impact:** Jumping and landing on terrain lacks shock absorption or knee-bend anticipation, feeling like a falling stone rather than an organic hero.

---

## Root Cause

- Direct movement architectures apply `controller.Move(moveDir * speed * dt)` without decoupling horizontal acceleration curves from vertical gravity.
- Rotation is computed solely as planar Y-axis heading without calculating angular turn rate ($d\theta/dt$) or applying rotational tilt (Z-axis banking).
- Landing events only reset vertical velocity without communicating impact kinetic energy to the visual mesh container.

---

## Solution ✅

### 1. Damped Horizontal Inertia (Acceleration & Foot-Slide Deceleration)
Separate horizontal velocity smoothing using `Vector3.SmoothDamp` with asymmetrical smooth times:
```csharp
// Fast responsive pickup (0.08s) vs smooth foot-slide stop (0.16s)
float smoothTime = targetVelocity.sqrMagnitude > 0.01f ? accelerationTime : decelerationTime;
currentHorizontalVelocity = Vector3.SmoothDamp(currentHorizontalVelocity, targetVelocity, ref horizontalVelocityRef, smoothTime);
controller.Move(currentHorizontalVelocity * Time.deltaTime);
```

### 2. Real-Time Angular Turn Rate & Body Banking
Calculate yaw delta per second, and tilt the visual mesh around the forward axis (Z-axis) proportional to sprinting speed:
```csharp
float turnDelta = Mathf.DeltaAngle(previousYRotation, transform.eulerAngles.y);
previousYRotation = transform.eulerAngles.y;
currentTurnRate = Mathf.Lerp(currentTurnRate, turnDelta / dt, dt * 10f);

float speedRatio = Mathf.Clamp01(currentHorizontalVelocity.magnitude / sprintSpeed);
float targetBank = Mathf.Clamp(-currentTurnRate * bankingStrength * speedRatio, -maxBankAngle, maxBankAngle);
currentBankAngle = Mathf.Lerp(currentBankAngle, targetBank, dt * 8f);
```

### 3. Damped Harmonic Landing Squash & Elastic Spring
Detect transition to grounded state with negative vertical velocity ($\Delta v_y < -3.5\text{ m/s}$), and squash the visual root container before restoring identity scale:
```csharp
// Damped harmonic oscillator curve: squash Y, expand X/Z, spring back
float decay = Mathf.Exp(-5.5f * progress);
float wave = Mathf.Sin(progress * Mathf.PI * 2.5f);
float offset = -maxSquash * decay * wave;

visualRoot.localScale = new Vector3(1f - offset * 0.45f, 1f + offset, 1f - offset * 0.45f);
```

### 4. Jump Apex Hang-Time
When airborne near the vertical apex ($\vert v_y \vert < 2.5\text{ m/s}$), scale gravity by $0.65\times$ to produce the iconic floaty anime hang-time.

---

## ⚠️ Pitfalls to Avoid

- **Collider Distortion:** NEVER scale or tilt the GameObject containing the `CharacterController` or combat hitboxes. Apply all banking angles and squash scales strictly to an inner `visualRoot` child transform.
- **Slope Sliding:** When decelerating on slopes, ensure downward grounding stickiness (`verticalVelocity = -2f`) remains active so the character controller does not lift off the terrain.
