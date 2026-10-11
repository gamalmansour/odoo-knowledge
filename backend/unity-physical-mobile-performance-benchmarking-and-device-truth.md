# Unity Physical Mobile Performance Benchmarking, Device Truth, and Measurement-First Discipline

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-24                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `mobile`, `performance`, `profiling`, `ios`, `metal`, `thermal`, `battery`, `csharp`

---

## Problem

In 3D mobile action-RPG development (e.g., Unity URP on iOS/Android):
1. **Premature Optimization:** Teams frequently degrade art assets (cutting textures from 2K to 512, stripping character skeleton bones, simplifying Cel Shaders) before capturing an empirical physical device baseline.
2. **False Hardware Representation:** Using macOS Unity Editor or Xcode iOS Simulator metrics as proxies for mobile performance. Simulators run on powerful desktop GPUs and do not exhibit mobile Tile-Based Deferred Rendering (TBDR) memory bandwidth constraints or thermal throttling.
3. **Fabricated Platform Claims:** Claiming multi-platform certification (e.g., Android) when no physical Android hardware is connected to the testing harness.

---

## Root Cause

- Desktop GPUs utilize immediate-mode rasterization with high thermal dissipation and dedicated VRAM, completely masking mobile GPU fragment overdraw and tile-load bottlenecks.
- Simulators and desktop engines do not emulate battery discharge curves, ambient device chassis heat, or OS-level thermal throttling (frequency stepping).
- Testing without fixed, repeatable scenarios leads to high variance and unrepeatable FPS numbers.

---

## Solution ✅

### 1. Four-Tier Hardware Execution Hierarchy
Strictly segregate physical hardware truth from virtualized environments:
- **DEVICE A (Primary Physical):** Certified commercial mobile device (e.g. iPhone 13 Pro Max with Apple A15 Bionic).
- **DEVICE B (Physical Android):** Explicitly mark as `BLOCKED — NO PHYSICAL DEVICE CONNECTED` when hardware is absent; never fabricate values.
- **DEVICE C (iOS Simulator):** Labeled `SUPPLEMENTARY ONLY` (smoke testing only).
- **DEVICE D (Unity Editor):** Labeled `SUPPLEMENTARY DIAGNOSTIC ONLY`.

### 2. Repeatable Deterministic Scenario Harness
Author a scenario driver (`Ahmed_MobilePerformanceScenario.cs`) that orchestrates fixed profiling slices (e.g. Idle, Sprint, Jump, Dash, Climb, Glide, 3-Hit Combos, Peak Load) without modifying gameplay mechanics:

```csharp
// Executes 14 deterministic scenarios for multi-run averaging
public class Ahmed_MobilePerformanceScenario : MonoBehaviour
{
    public enum ScenarioID { BASE_IDLE, SPRINT, COMBAT_ATTACK_2, PEAK_LOAD /* ... */ }
    [SerializeField] private float scenarioDurationSeconds = 15.0f;
    // Coordinates input repeatably without faking FPS or bypassing systems
}
```

### 3. Measurement-First Discipline
- Capture empirical baseline across 14 scenarios before altering any art or shader assets.
- Execute 15-minute thermal stress runs to observe frequency stepping ($59.8 \to 56.8\text{ FPS}$).
- Measure battery consumption under controlled conditions ($50\%$ fixed brightness, disconnected charger).
- Audit memory across $\ge 4$ scene reloads to certify zero leak drift ($\le 2\text{ MB}$).

---

## ⚠️ Pitfalls

- **Simulator ≠ Physical Device:** Never present simulator FPS as mobile performance validation.
- **Fabricated Platform Metrics:** If Android physical hardware is not attached, report status as `BLOCKED` rather than guessing numbers.
- **Shipping Dev Tooling:** Always wrap profiling HUDs in `#if DEVELOPMENT_BUILD || UNITY_EDITOR` to prevent runtime overhead in release builds.
- **Optimizing Before Measuring:** Changing assets prior to establishing a baseline destroys the ability to measure real performance deltas.

---

## Verification

```bash
python3 validate_m64_performance_baseline.py
# Verify:
# - Build manifest and 14 scenarios exist
# - Physical iPhone build metadata present
# - Android status explicitly reported as BLOCKED
# - Editor results quarantined as supplementary
# - 16/16 checks passed
```

---

## References

- Related file: `backend/unity-urp-cel-shading-shadows-and-mobile-performance.md`
- Related file: `backend/unity-gameplay-animation-event-adapter-and-hitstop-sync.md`
- Deliverable: `/Docs/m6.4a-physical-mobile-performance-baseline.md`
- Deliverable: `/M6.4A_Performance_Baseline.json`
