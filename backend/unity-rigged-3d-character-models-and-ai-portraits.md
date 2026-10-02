# Unity 6 Rigged 3D Character Models, Nested Collider Stripping & AI Face Portraits

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `3d-models`, `fbx`, `rigged-characters`, `nested-colliders`, `ai-portraits`, `hud`, `genshin`

---

## Problem

When upgrading a game prototype from primitive geometric placeholders ("programmer art" cubes/spheres) to commercial rigged 3D models (FBX):
1. Raw FBX imports often contain internal MeshColliders or BoxColliders that conflict with the parent entity's `CharacterController`, producing severe physics jitter or launching characters into the stratosphere.
2. In standalone player builds (macOS/Android), loading textures or models via relative disk paths (`Application.dataPath`) fails because the asset database is packed.
3. If FBX files are added outside of Unity while the editor is closed, `.meta` files are missing until batchmode import runs, causing `Resources.Load` to return `null`.

## Root Cause

1. Complex 3D rigs exported from Blender or asset packages often bake collision volumes into secondary bones or accessory nodes.
2. Standalone Unity players pack assets into proprietary archive formats; only assets located within an `Assets/Resources/` folder with generated `.meta` GUIDs can be resolved dynamically via `Resources.Load<T>()`.

## Solution ✅

### 1. Robust Resources Layout & Batchmode Import
Place models and textures in `Assets/Resources/Models/` and `Assets/Resources/Textures/`. Trigger an editor batchmode pass to ensure Unity compiles shaders, reduces animation keyframes, and generates `.meta` GUIDs:

```bash
/Applications/Unity/Hub/Editor/6000.6.0f1/Unity.app/Contents/MacOS/Unity \
  -quit -batchmode -nographics \
  -projectPath "/path/to/unity_project" \
  -logFile /tmp/unity_import.log
```

### 2. Nested Collider Stripping & Dynamic Material Mapping
When instantiating the 3D visual root beneath a controller GameObject, strip child colliders defensively so physics is exclusively governed by the parent `CharacterController`:

```csharp
private GameObject CreateCharacterEntity(string entityName, string modelPath, string texturePath, Vector3 position, Vector3 scale, PrimitiveType fallbackPrimitive)
{
    GameObject prefab = Resources.Load<GameObject>(modelPath);
    if (prefab != null)
    {
        GameObject root = new GameObject(entityName);
        root.transform.position = position;
        GameObject visual = Instantiate(prefab, root.transform, false);
        visual.transform.localPosition = Vector3.zero;
        visual.transform.localScale = scale;

        Texture2D tex = Resources.Load<Texture2D>(texturePath);
        if (tex != null)
        {
            Shader cel = Shader.Find("MeenYsed/GenshinCelShading") ?? Shader.Find("Universal Render Pipeline/Lit");
            foreach (var r in visual.GetComponentsInChildren<Renderer>(true))
            {
                Material m = new Material(cel);
                m.mainTexture = tex;
                if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex);
                r.material = m;
            }
        }

        // Clean parent physics: strip nested colliders
        foreach (var c in visual.GetComponentsInChildren<Collider>(true))
        {
            Destroy(c);
        }
        return root;
    }
    // Fallback gracefully to primitive if resources are missing
    return GameObject.CreatePrimitive(fallbackPrimitive);
}
```

### 3. High-Resolution AI Face Portraits on HUD Cards
Combine Google AI-generated high-res 2D face textures with `RawImage` or GUI draw routines in party-switching HUDs to give instant character identity to 3D models:

```csharp
GameObject avatarObj = new GameObject("Hero_Avatar_Portrait");
avatarObj.transform.SetParent(card.transform, false);
var rawImg = avatarObj.AddComponent<RawImage>();
rawImg.texture = Resources.Load<Texture2D>("Textures/" + faceFiles[heroIndex]);
```

## ⚠️ Pitfalls

- **Do Not Leave Nested Colliders:** Never allow FBX child nodes to keep active colliders when a parent has a `CharacterController`. It causes continuous false ground hits and velocity stutter.
- **Always Keep Defensive Fallback:** If `Resources.Load` fails due to asset pipeline issues, falling back to procedural meshes prevents `NullReferenceException` crashes.

## Verification

Run automated E2E testing to ensure zero runtime exceptions, intact Metal GPU pipelines, and responsive character switching:

```bash
python3 test_e2e_meenysed.py
```
