# Unity Procedural Audio Synthesis & URP Post-Processing Stripping Safeguards

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `audio`, `procedural-audio`, `urp`, `post-processing`, `bloom`, `aces`, `mobile`

---

## Problem

1. **Missing Audio Assets in Standalone Builds:** Relying on external audio files (`.mp3`, `.wav`) under `Resources/` often results in silent builds or `NullReferenceException` if sound assets are moved, stripped, or not yet imported by the sound design team.
2. **URP Post-Processing Pass Failure Warnings:** When exporting a standalone Unity build, URP strips unreferenced post-processing shaders (such as `GaussianDepthOfField`, `BokehDepthOfField`, or `PaniniProjection`). If a default template scene's `VolumeProfile` has these effects marked active, URP prints repeated warnings and may skip downstream post-processing passes entirely:
```
Shader 'Hidden/Universal Render Pipeline/GaussianDepthOfField' is not supported or has been stripped from the build. PostProcessing render passes will not execute.
```

---

## Root Cause

- External asset pipelines decouple audio playback logic from audio file availability. Without a procedural fallback, missing audio assets fail silently or throw exceptions.
- URP Shader Stripping operates aggressively during standalone player compilation to reduce binary size. If a global Volume references stripped passes, the render pipeline halts those passes.

---

## Solution ✅

### 1. Procedural Waveform Audio Synthesis
Implement procedural audio synthesis using `AudioClip.Create(...)` to mathematically construct sound waves for weapon swings, bow twangs, spell casts, and looping BGM drones:

```csharp
// Example: Crisp weapon swoosh synthesis
private AudioClip GenerateSwordSwingClip()
{
    float duration = 0.16f;
    int numSamples = (int)(duration * SAMPLE_RATE);
    float[] samples = new float[numSamples];

    for (int i = 0; i < numSamples; i++)
    {
        float t = (float)i / SAMPLE_RATE;
        float progress = t / duration;
        float env = Mathf.Sin(progress * Mathf.PI) * (1f - progress);

        float noise = (UnityEngine.Random.value * 2f - 1f) * 0.4f;
        float freq = Mathf.Lerp(800f, 220f, progress);
        float tone = Mathf.Sin(2f * Mathf.PI * freq * t) * 0.6f;

        samples[i] = (noise + tone) * env * 0.8f;
    }

    var clip = AudioClip.Create("Proc_SwordSwing", numSamples, 1, SAMPLE_RATE, false);
    clip.SetData(samples, 0);
    return clip;
}
```

### 2. Runtime Profile Isolation for Post-Processing
Create a clean runtime `VolumeProfile` containing only the supported, production-ready passes (ACES Tonemapping, Bloom, Color Adjustments, Vignette), and programmatically disable any leftover template volumes:

```csharp
// Disable conflicting template volumes
var oldVolumes = FindObjectsByType<Volume>(FindObjectsSortMode.None);
foreach (var v in oldVolumes)
{
    if (v != globalVolume) v.enabled = false;
}

// Construct clean isolated runtime profile
runtimeProfile = ScriptableObject.CreateInstance<VolumeProfile>();
var tonemapping = runtimeProfile.Add<Tonemapping>(true);
tonemapping.mode.overrideState = true;
tonemapping.mode.value = TonemappingMode.ACES;

var bloom = runtimeProfile.Add<Bloom>(true);
bloom.intensity.overrideState = true;
bloom.intensity.value = 1.25f;
bloom.threshold.overrideState = true;
bloom.threshold.value = 0.85f;
```

---

## ⚠️ Pitfalls to Avoid

- **Sample Rate Memory Pitfall:** Generating procedural clips at 48000Hz or stereo needlessly multiplies memory. Using `22050Hz` mono for procedural clips provides crystal-clear synthesized sound with less than `2 MB` total RAM footprint for all SFX and looping BGMs combined.
- **Audio Thread Allocation:** Never call `AudioClip.Create` or `SetData` inside hot gameplay loops (`Update`). Synthesize all fallback clips once during `Awake()` and cache their references.
