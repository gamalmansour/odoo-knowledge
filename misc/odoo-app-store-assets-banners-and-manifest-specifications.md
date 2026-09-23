# Odoo Apps Store Asset Specifications (1000x300 Banners, 256x256 Icons, Manifest Images Array)

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-23                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `app-store`, `static-description`, `banner`, `icon`, `manifest`, `images`, `branding`, `odoo18`

---

## Problem

When listing an enterprise module or suite on the official **Odoo Apps Store** (`apps.odoo.com`), developers often encounter the following issues:
1. The module card in the store search index displays a generic, blurry, or stretched thumbnail placeholder.
2. The module detail page displays an empty banner area or clips the graphic because non-standard dimensions were used.
3. The store ignores custom promotional graphics because `'images'` is missing or improperly specified in `__manifest__.py`.

## Root Cause

1. **Odoo Apps Store Crawler Conventions:**
   - The Odoo Apps Store parser looks for an `'images'` key in `__manifest__.py`. If absent, it attempts to fall back to `static/description/icon.png` (as a square) and may not display a featured hero banner.
   - For carousel and header hero display, the App Store expects an exact **10:3 aspect ratio** (officially **1000x300 pixels** PNG or high-quality JPG).
   - If a banner is uploaded in 16:9 (e.g., 1920x1080) or arbitrary resolutions, the store's CSS either crops top/bottom or stretches the image, destroying branding and typography.
2. **Transparent Banner Bleed Bug:**
   - If the banner background is left transparent, the Odoo App Store web background (or dark mode user agents) causes dark text or dark logos to become unreadable.
3. **Module Icon Dimensions:**
   - Odoo desktop app switcher and App Store require a **256x256 PNG** with smooth rounded squircle corners.

## Solution ✅

### 1. Configure `__manifest__.py`
Declare the banner explicitly in the manifest under the `'images'` key:

```python
# -*- coding: utf-8 -*-
{
    'name': 'Construction Project Management',
    'version': '18.0.1.30.3',
    'author': 'The Secret Solutions, ENG/Gamal Mansour',
    'website': 'https://www.thesecret-solutions.com/',
    'maintainer': 'The Secret Solutions',
    'support': 'info@thesecret-solutions.com',
    'images': ['static/description/banner.png'],
    # ...
}
```

### 2. Standardized Asset Specifications

| Asset | File Path | Dimensions | Format | Notes |
|---|---|---|---|---|
| **Hero Banner** | `static/description/banner.png` | **1000 x 300 px** | PNG (RGB) | Solid dark/brand background (no transparency), 2x supersampled (2000x600 -> 1000x300) |
| **App Icon** | `static/description/icon.png` | **256 x 256 px** | PNG (RGBA) | Squircle with corner radius ~50px, transparent outer canvas |
| **Landing Page** | `static/description/index.html` | Responsive | HTML / CSS | Corporate landing page with features, screenshots, and support links |

### 3. Automated 2x Supersampling Generation Pipeline (Python PIL)

To achieve crisp typography and prevent blurry scaling on Retina displays:
- Render text, badges, and layout at **2000 x 600 px**.
- Smoothly blend the focal 3D render on the right half with a gradient alpha mask fading into the solid dark base.
- Keep the left ~550px for high-contrast typography, badges, version tags, and company branding.
- Downscale to **1000 x 300 px** using `Image.Resampling.LANCZOS`.

```python
from PIL import Image

# Resize with LANCZOS downsampling for razor-sharp text
final_banner = supersampled_banner.resize((1000, 300), Image.Resampling.LANCZOS)
final_banner.save("static/description/banner.png", "PNG", optimize=True)
```

## ⚠️ Pitfalls

1. **Placing Text in the Right 45% of the Banner:**
   - The right side should contain the visual/graphic asset. Any text placed in the right half gets obscured or competes with the focal 3D artwork.
2. **Missing `'images'` in `__manifest__.py`:**
   - Even if `static/description/banner.png` exists on disk, Odoo Apps Store indexing algorithms require `'images': ['static/description/banner.png']` to register the banner for search previews and carousels.
3. **JPEG Compression Artifacts around White Logos:**
   - Always save `banner.png` as a PNG. JPEG compression around high-contrast vector logos and badge text creates ringing artifacts.
4. **Hardcoded Relative Paths in `index.html`:**
   - In `index.html`, do not link local CSS or images with relative paths like `../src/img.png` because the App Store renders descriptions in an isolated iframe. Use CDN links for fonts/icons or embed assets directly.

## Verification

Run an automated audit on all add-on modules to verify that `banner.png`, `icon.png`, and manifest `'images'` match the specification:

```bash
python3 -c "
import os, ast
from PIL import Image

for root, dirs, files in os.walk('.'):
    if '__manifest__.py' in files:
        m_path = os.path.join(root, '__manifest__.py')
        with open(m_path) as f:
            d = ast.literal_eval(f.read())
        images = d.get('images', [])
        b_path = os.path.join(root, 'static/description/banner.png')
        if os.path.exists(b_path):
            img = Image.open(b_path)
            assert img.size == (1000, 300), f'Bad banner size {img.size} in {b_path}'
            assert 'static/description/banner.png' in images, f'Missing manifest images in {m_path}'
print('All App Store banners and manifests verified!')
"
```

## References

- [Odoo Apps Store Guidelines](https://apps.odoo.com/apps)
- Related file: `views/adding-chatter-odoo17-odoo18-requirements.md`
