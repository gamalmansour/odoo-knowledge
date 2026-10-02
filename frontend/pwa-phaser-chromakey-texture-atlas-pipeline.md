# Phaser Texture Atlas & AI 3D Asset Pipeline in Odoo PWAs

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 16, 17, 18, 19, All                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `pwa`, `phaser`, `chromakey`, `texture-atlas`, `3d-art`, `cache-busting`

---

## Problem

When integrating newly generated 3D AI sprites into an Odoo-hosted Progressive Web App (PWA) that uses Phaser 3 for canvas rendering:
1. AI generators produce assets on solid backgrounds (e.g., magenta `#FF00FF`), leading to harsh magenta fringing and halo artifacts around curved/antialiased edges if naive threshold transparency is used.
2. Replacing individual sprites or altering texture atlas sheet dimensions can silently break Phaser animations, sprite origins, or in-game scaling (`setScale()`).
3. Mobile PWA service workers cache old atlas images and JSON manifests aggressively, preventing end-users from seeing new 3D assets without manual cache clears.

## Root Cause

- Naive RGB thresholding does not account for semi-transparent edge pixels where foreground colors blend into the background color (fringing/spill).
- Phaser scenes often hardcode frame-based scaling assumptions (e.g., expecting 128x128 bounding boxes). Directly packing arbitrary-sized PNGs causes sprites to appear distorted or misaligned in existing scenes.
- Service Workers check cache keys based on manifest version hashes or hardcoded strings. If the service worker file (`sw.js`) is not version-bumped, the client browser continues serving stale cached sprites.

## Solution ✅

Implement an automated pre-processing and atlas packing pipeline in Python using `Pillow` and `numpy`:

```python
# tools/build_atlas.py
import json
import numpy as np
from PIL import Image

def chromakey_despill(img: Image.Image, bg_rgb=(255, 0, 255), tolerance=45.0, feather=15.0) -> Image.Image:
    """Removes solid background, computes soft alpha feathering, and suppresses color spill."""
    arr = np.array(img.convert("RGBA"), dtype=np.float32)
    diff = np.sqrt(np.sum((arr[:, :, :3] - bg_rgb) ** 2, axis=2))
    
    # Smooth alpha ramp
    alpha = np.clip((diff - tolerance) / max(feather, 1.0), 0.0, 1.0) * 255.0
    arr[:, :, 3] = alpha
    
    # Despill: clamp magenta channel towards max green/blue
    near_bg = diff < (tolerance + feather * 2.0)
    arr[near_bg, 0] = np.minimum(arr[near_bg, 0], np.maximum(arr[near_bg, 1], arr[near_bg, 2]) * 1.05)
    
    out = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out
```

Fit processed sprites with aspect-ratio preservation into standardized cell grids (e.g. 128x128) using `Image.Resampling.LANCZOS`, append new rows to `atlas.png`, and record updated frame coordinates into `atlas.json`.

Finally, always bump the cache version in `sw.js` and `app.js`:
```javascript
const VERSION = "0.4.0"; // Bump version on every asset rebuild
```

## ⚠️ Pitfalls

- **Avoid modifying game sprite origins:** If Phaser creates sprites centered at `(x, y)`, ensure the replacement sprite is centered within its atlas frame cell.
- **Service Worker Stale Cache:** Always verify that `sw.js` is updated whenever `atlas.png` or `atlas.json` changes.
- **Aspect Ratio Distortion:** Never force-stretch cropped sprites directly to 128x128; calculate scaling factors to maintain original aspect ratios before pasting onto the canvas cell.

## Verification

1. Run automated build script:
```bash
python3 tools/build_atlas.py
```
2. Verify that `atlas.png` has no magenta fringing over dark backgrounds (`#191614`).
3. Confirm in the browser console that the Service Worker installs the new cache version without errors.

## References

- Phaser 3 Texture Manager Documentation
- Odoo Web Assets & PWA Caching Guidelines
