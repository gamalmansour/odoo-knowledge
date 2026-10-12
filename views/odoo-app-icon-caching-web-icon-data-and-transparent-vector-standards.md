# Odoo App Icon Caching in `ir.ui.menu.web_icon_data` & Transparent Vector Standards

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | views                                      |
| Odoo Versions | 16, 17, 18, 19                             |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-12                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `web_icon`, `icon.png`, `ir.ui.menu`, `web_icon_data`, `app-switcher`, `ui`, `caching`

---

## Problem

After replacing an add-on's application icon at `<module>/static/description/icon.png`, the Odoo web client Home Screen / App Switcher continues to render the **old** icon even after hard-refreshing the browser (`Ctrl+F5` / `Cmd+Shift+R`) or restarting the Odoo service.

Furthermore, naive background removal scripts (e.g. converting all pixels with RGB > 240 to `alpha = 0`) inadvertently punch transparent holes through legitimate white internal elements such as inspection clipboards, paper documents, and clock faces.

## Root Cause

1. **Persistent Menu Icon Caching:** In Odoo, top-level menus (`ir.ui.menu` with `parent_id = False`) store a precomputed base64 data URI in `ir.ui.menu.web_icon_data`. This field is only computed upon menu creation or when the `web_icon` field is explicitly written to via `_compute_web_icon_data`. Replacing the image file on disk does **not** automatically invalidate or recompute `ir.ui.menu.web_icon_data` in the database.
2. **Module Record Cache:** `ir.module.module` similarly stores a binary copy in `icon_image`.
3. **HTTP Static Caching:** Static assets under `/static/description/` are served with aggressive HTTP caching (`Cache-Control: public, max-age=604800`).

## Solution ✅

### 1. Invalidate & Recompute `ir.ui.menu.web_icon_data` via Python/Shell

Execute this script via Odoo shell or python environment to force re-reading the image from disk and updating the stored base64 payload:

```python
with env.cr.savepoint():
    menus = env['ir.ui.menu'].search([('parent_id', '=', False)])
    for m in menus:
        if m.web_icon and '<target_module>' in m.web_icon:
            # Writing web_icon triggers _compute_web_icon_data and clears registry cache
            m.write({'web_icon': m.web_icon})
            
    # Also update ir.module.module
    mod = env['ir.module.module'].search([('name', '=', '<target_module>')], limit=1)
    if mod:
        mod._update_icon()  # Or re-read static/description/icon.png
    env.cr.commit()
```

### 2. Icon Dimensions & Transparent Vector Best Practices

To ensure full harmony with standard Odoo 18 / 19 webclient app switcher tiles:
- **Canvas:** Exactly 256 × 256 pixels, RGBA format.
- **Outer Background:** Completely transparent (`alpha = 0`). Do not include dark rounded square tiles, mockups, or container boxes.
- **Glyph Bounding Box:** Visual content should be centered at (128, 128) with a bounding box of approximately `(45, 45, 215, 215)` (~150–170px width/height).
- **Internal White Preservation:** When removing white backgrounds from generated or vector-exported artwork, use **seed-based border flood-fill** from the canvas edges instead of global color thresholding. This keeps interior white paper sheets, document lines, and clock faces fully opaque (`alpha = 255`).

```python
from collections import deque
import numpy as np
from PIL import Image

def extract_transparent_glyph(im: Image.Image, threshold: int = 245) -> Image.Image:
    arr = np.array(im.convert('RGB'))
    H, W, _ = arr.shape
    is_white = (arr[:, :, 0] >= threshold) & (arr[:, :, 1] >= threshold) & (arr[:, :, 2] >= threshold)
    
    # 2D BFS flood-fill strictly from the 4 outer borders
    visited = np.zeros((H, W), dtype=bool)
    queue = deque()
    for r in range(H):
        for c in [0, W - 1]:
            if is_white[r, c] and not visited[r, c]:
                visited[r, c] = True; queue.append((r, c))
    for c in range(W):
        for r in [0, H - 1]:
            if is_white[r, c] and not visited[r, c]:
                visited[r, c] = True; queue.append((r, c))
    while queue:
        r, c = queue.popleft()
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and not visited[nr, nc] and is_white[nr, nc]:
                visited[nr, nc] = True; queue.append((nr, nc))
                
    alpha = np.where(visited, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack((arr, alpha)), 'RGBA')
```

## ⚠️ Pitfalls

- **Module Upgrade Without File Hash Change:** Running `-u <module>` without changing file timestamps or manifest version may cause the browser to serve the cached icon from browser cache due to HTTP 304 Not Modified. Always bump the patch version or use hard-refresh.
- **Card-inside-Card Antipattern:** Avoid drawing an app icon squircle/rounded rectangle inside `icon.png`. Odoo's web client already wraps app icons inside standard rounded cards with subtle drop shadows. Adding an internal card creates an awkward "double card" look.
- **Font/Text in App Icons:** Never put fine explanatory text or module names inside `icon.png` (e.g. "V18 - The Secret Solutions"). The web client displays the module title directly underneath the icon.

## Verification

```bash
# Verify static HTTP 200 and updated Content-Length:
curl -s -I "http://localhost:8069/<module>/static/description/icon.png"

# Verify web_icon_data length in Postgres:
python3 -c "
# Check len(ir_ui_menu.web_icon_data) matches new compressed size
"
```

## References

- Odoo Core: `odoo/addons/base/models/ir_ui_menu.py` (`_compute_web_icon_data`)
- Odoo Webclient: `addons/web/static/src/core/tree_editor/` and App Switcher icon rendering
