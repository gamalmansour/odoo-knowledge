# Unity URP Cel-Shading Shadowmap Sampling & Mobile Inverted Hull Performance Safeguards

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | backend                                    |
| Odoo Versions | 18, 19                                     |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity`, `urp`, `shaders`, `cel-shading`, `shadows`, `inverted-hull`, `mobile`, `tbdr`, `overdraw`

---

## Problem

1. **Floating Characters (Missing Shadowmap Sampling in Custom Shaders):** Custom HLSL Cel-Shaders in Unity URP declaring `#pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE` still render characters that do not receive dynamic shadows or environment shadows. The character appears to float unnaturally over the terrain.
2. **TBDR Overdraw Stalls on Mobile:** The classic "Inverted Hull" technique (extruding vertex normals in a separate pass to draw anime outlines) doubles the vertex count and rasterization load. On mobile GPUs using Tile-Based Deferred Rendering (TBDR, like Apple A-Series and ARM Mali), applying outlines without vertex masking or distance culling causes severe memory bus bandwidth saturation and thermal throttling.
3. **Runtime Primitive Instantiation Blocks Batching:** Instantiating world structures procedurally at runtime using `GameObject.CreatePrimitive` generates unbatched dynamic mesh renderers, preventing static batching, lightmap baking, and occlusion culling trees from functioning.

---

## Root Cause

1. In URP's `Lighting.hlsl`, calling `GetMainLight()` without passing shadow coordinates returns a dummy light structure where `shadowAttenuation = 1.0`. To receive shadows, the vertex shader must output `TransformWorldToShadowCoord(positionWS)` and the fragment shader must call `GetMainLight(shadowCoord)`.
2. Inverted hull outlines rasterize the backfaces of the entire mesh. On intricate character models with fingers, eyes, and layered clothing, internal vertices create massive sub-pixel overdraw and visual artifacts ("exploding" thick black outlines on small features).
3. Unity's static rendering pipeline (Lightmapping, Static Batching, Occlusion Culling) requires static flags and pre-calculated data stored in the scene asset. Primitives spawned in `Start()` via C# are dynamic by definition.

---

## Solution ✅

### 1. Correct URP Shadow Coordinate Passing in HLSL

In the Cel-Shader's forward lit pass, pass the shadow coordinate from vertex to fragment shader:

```hlsl
struct Varyings
{
    float4 positionCS : SV_POSITION;
    float2 uv         : TEXCOORD0;
    float3 normalWS   : TEXCOORD1;
    float3 viewDirWS  : TEXCOORD2;
    float3 positionWS : TEXCOORD3;
    float4 shadowCoord: TEXCOORD4; // Pass shadow coordinate
};

Varyings vert(Attributes input)
{
    Varyings output;
    VertexPositionInputs vertexInput = GetVertexPositionInputs(input.positionOS.xyz);
    VertexNormalInputs normalInput = GetVertexNormalInputs(input.normalOS);

    output.positionCS = vertexInput.positionCS;
    output.positionWS = vertexInput.positionWS;
    output.normalWS = normalInput.normalWS;
    output.viewDirWS = GetWorldSpaceNormalizeViewDir(vertexInput.positionWS);
    output.uv = input.uv;

    // Compute shadow coordinates with cascade support
    output.shadowCoord = TransformWorldToShadowCoord(vertexInput.positionWS);
    return output;
}

half4 frag(Varyings input) : SV_Target
{
    // Sample main light WITH shadow attenuation
    Light mainLight = GetMainLight(input.shadowCoord);
    float shadow = mainLight.shadowAttenuation;

    // Apply shadow directly to the cel-shaded ramp
    float lightIntensity = (dot(input.normalWS, mainLight.direction) + 1.0) * 0.5;
    float celStep = smoothstep(_ShadowThreshold - _ShadowSmoothness, _ShadowThreshold + _ShadowSmoothness, lightIntensity * shadow);
    
    // ...
}
```

### 2. Vertex Color Masking & Distance Culling for Outlines

In the Inverted Hull pass, modulate the extrusion thickness using the vertex color (Red channel) and distance fade:

```hlsl
Varyings vertOutline(Attributes input)
{
    Varyings output;
    float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
    float distToCamera = distance(positionWS, _WorldSpaceCameraPos);

    // Fade outline to 0 past 15 meters to eliminate mobile overdraw
    float distanceFade = saturate(1.0 - (distToCamera - 10.0) / 5.0);
    
    // Vertex color R channel controls outline thickness (0 = no outline on eyes/fingers)
    float mask = input.color.r;
    float finalWidth = _OutlineWidth * mask * distanceFade;

    float3 normalOS = normalize(input.normalOS);
    float3 extrudedOS = input.positionOS.xyz + normalOS * finalWidth;
    output.positionCS = TransformObjectToHClip(extrudedOS);
    return output;
}
```

### 3. Static Prefab Baking over Runtime Spawning

Always replace runtime `GameObject.CreatePrimitive` world generation with pre-authored static prefabs marked `ContributeGI` and `StaticBatching`:
- Combine small modular pieces with shared texture atlases.
- Bake lightmaps using Subtractive or Shadowmask mode.
- Use GPU Instancing for foliage and repetitive props.

---

## ⚠️ Pitfalls

- **Shadow Acne on Low-Poly Meshes:** Cel-shading exaggerates shadow acne. Set the directional light's Normal Bias to `0.4` and Depth Bias to `0.05` in URP asset settings.
- **Translucent Eyes / Eyebrows Behind Outlines:** Render the face and eyes in a separate material pass with `ZTest LEqual` and zero outline width to ensure eyes remain crisp and unobstructed.
