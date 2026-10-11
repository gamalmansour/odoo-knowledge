# Three.js WebGL Lifecycle Management and Billboard Sprites in OWL Client Actions

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | frontend                                   |
| Odoo Versions | 17, 18, 19                                 |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-16                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `owl`, `threejs`, `webgl`, `memory-leak`, `billboard-sprites`, `lifecycle`

---

## Problem

When embedding Three.js WebGL architectural digital twins or 3D visualizers inside an Odoo OWL Client Action, navigating between the 3D action and standard Odoo form/list views leads to progressive browser memory consumption (VRAM bloat) and eventually crashes the browser tab with:

```
WARNING: WebGL: CONTEXT_LOST_WEBGL: loseContext: context lost
Uncaught (in promise) Error: WebGL context was lost.
```

Additionally, 2D HTML/CSS overlays used for unit numbers either fail to follow 3D orbital perspective or clip awkwardly through solid architectural walls.

## Root Cause

1. **GPU/VRAM Leakage:** Three.js objects (Meshes, Geometries, Materials, and Textures) reside on both CPU JavaScript heap and GPU VRAM. Garbage collection in JavaScript does **NOT** release GPU textures or WebGL buffers. If the OWL component is destroyed without explicitly calling `.dispose()` on all geometries, textures, materials, controls, and renderer, the WebGL contexts remain allocated until the tab crashes.
2. **Animation Loop Orphan:** If `cancelAnimationFrame(this.animFrameId)` is not invoked upon component unmount, the render loop continues running indefinitely in the background, consuming 100% of a CPU/GPU core.
3. **Number Label Perspective:** Using screen-space HTML tags for unit numbers ignores camera depth. True 3D spatial labels require `THREE.Sprite` with dynamic 2D canvas textures and `depthTest: true` so they face the camera 360° while naturally occluding behind intervening floors and walls.

## Solution ✅

### 1. Robust Lifecycle Cleanup in `onWillUnmount()`

In the OWL Component, store references to the animation frame and event listeners, and traverse the scene graph to dispose all WebGL resources cleanly:

```javascript
import { Component, onMounted, onWillUnmount } from "@odoo/owl";

export class UnitMatrix3D extends Component {
    setup() {
        this.animFrameId = null;

        onMounted(() => {
            this.initThreeEngine();
        });

        onWillUnmount(() => {
            this.cleanupThreeEngine();
        });
    }

    cleanupThreeEngine() {
        // 1. Cancel animation loop
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
        }

        // 2. Remove DOM listeners
        const container = this.canvasContainerRef.el;
        if (container) {
            container.removeEventListener("mousemove", this._onMouseMove);
            container.removeEventListener("click", this._onClick);
        }
        window.removeEventListener("resize", this._onResize);

        // 3. Dispose OrbitControls
        if (this.controls) {
            this.controls.dispose();
        }

        // 4. Deep traverse scene and dispose GPU memory
        if (this.scene) {
            this.scene.traverse((obj) => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach((m) => {
                            if (m.map) m.map.dispose();
                            m.dispose();
                        });
                    } else {
                        if (obj.material.map) obj.material.map.dispose();
                        obj.material.dispose();
                    }
                }
            });
        }

        // 5. Dispose WebGL Renderer
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}
```

### 2. High-Resolution Billboard Sprites with Depth Testing

Generate a dynamic 2D canvas and wrap it in a `THREE.CanvasTexture` on a `THREE.Sprite`:

```javascript
createUnitBadgeSprite(unitNumber, state) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 128;
    const ctx = canvas.getContext("2d");

    // Rounded luxury badge background
    ctx.fillStyle = "rgba(10, 15, 29, 0.92)";
    ctx.roundRect ? ctx.roundRect(16, 20, 224, 88, 24) : ctx.rect(16, 20, 224, 88);
    ctx.fill();

    // Unit number text
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 46px Cairo, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(unitNumber, 142, 65);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;

    const spriteMat = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: true // Automatically occludes behind closer walls
    });

    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(1.4, 0.7, 1);
    return sprite;
}
```

## ⚠️ Pitfalls

- **Do NOT rely on JS garbage collector:** Even if you drop `this.scene = null`, the WebGL context retains textures in VRAM. Explicit traversal with `.dispose()` is mandatory.
- **Local Assets vs CDN:** Always bundle `three.min.js` and `OrbitControls.js` in `web.assets_backend` under `static/src/lib/` to avoid external CDN security blocks or offline demo failures.
- **Layout Wrap:** As noted in `frontend/owl_action_layout_hidden.md`, always wrap client actions in `<Layout display="{ controlPanel: false }">` to avoid navbar overlap in Odoo 18.

## Verification

1. Open DevTools Memory tab and inspect JS Heap / WebGL Memory.
2. Navigate into the 3D Unit Matrix client action, orbit, explode floors, and click units.
3. Navigate back to standard Odoo list/form views 20 times.
4. Verify WebGL contexts and memory footprint return to baseline with zero memory leak.

## References

- Related file: `frontend/owl_action_layout_hidden.md`
- Related file: `frontend/owl-client-action-scrolling.md`
