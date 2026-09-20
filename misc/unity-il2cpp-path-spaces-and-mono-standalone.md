# Unity 6 IL2CPP Bee Build Fails on Paths with Spaces and Mono Standalone Fallback

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-09-20                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity6`, `il2cpp`, `bee_backend`, `spaces_in_path`, `symlinks`, `mono`, `standalone_osx`

---

## Problem

When building a Unity 6 (6000.6.0f1) project targeting platforms requiring IL2CPP (such as Android ARM64 or WebGL) on macOS, the build fails during the `bee_backend` phase with:

```
Either unknown arguments were used or one or more assemblies could not be found : 
    Ysed/Phoenix_Vertical_Slice/Library/Bee/artifacts/...
```

Furthermore, unquoted paths containing spaces cause il2cpp argument splitting where `Meen Ysed` is split into two separate arguments, causing command-line parsing failures or SIGSEGV crashes.

## Root Cause

1. **Space in Project Path:** Unity's internal `bee_backend` / Tundra build pipeline on Unix/macOS passes paths to `il2cpp` without escaping or enclosing directory arguments (like `--generatedcppdir=...`, `--symbols-folder=...`, `--profiler-output-file=...`) in quotes. When the folder path contains spaces (e.g. `/Users/.../Meen Ysed/...`), arguments are split at whitespace.
2. **Canonical Path Resolution:** Symlinking the entire root directory does not fool .NET/Mono runtime because `Directory.GetCurrentDirectory()` resolves symlinks back to the canonical filesystem path with spaces.
3. **Mono vs IL2CPP:** Standalone macOS desktop builds use the Mono runtime by default, which bypasses `il2cpp` completely and produces stable 60 FPS native binaries without tripping on IL2CPP compiler issues.

## Solution ✅

### 1. Structural Fix for Spaces in Unity Projects
Create a real root folder without spaces and symlink only the internal project assets:

```bash
mkdir -p /path/without/spaces/UnityProject
ln -s "/path/with spaces/UnityProject/Assets" /path/without/spaces/UnityProject/Assets
ln -s "/path/with spaces/UnityProject/Packages" /path/without/spaces/UnityProject/Packages
ln -s "/path/with spaces/UnityProject/ProjectSettings" /path/without/spaces/UnityProject/ProjectSettings
```

Open and build Unity from `/path/without/spaces/UnityProject`. This ensures `Library/Bee` and all generated build artifacts live under a path containing zero spaces.

### 2. Preserve Managed Types with `link.xml`
Create `Assets/link.xml` to prevent IL2CPP from stripping generic type definitions needed by reflection:

```xml
<linker>
  <assembly fullname="Assembly-CSharp" preserve="all"/>
  <assembly fullname="Unity.RenderPipelines.Universal.Runtime" preserve="all"/>
  <assembly fullname="Unity.RenderPipelines.Core.Runtime" preserve="all"/>
  <assembly fullname="Unity.InputSystem" preserve="all"/>
  <assembly fullname="Unity.TextMeshPro" preserve="all"/>
  <assembly fullname="UnityEngine" preserve="all"/>
</linker>
```

### 3. Immediate Desktop Playability (Mono Standalone)
For instant local testing and demos on Apple Silicon Mac, build the Standalone OSX player:

```csharp
BuildPlayerOptions buildPlayerOptions = new BuildPlayerOptions
{
    scenes = new string[] { "Assets/Scenes/SampleScene.unity" },
    locationPathName = "Builds/macOS/MeenYsed.app",
    target = BuildTarget.StandaloneOSX,
    options = BuildOptions.None
};
BuildPipeline.BuildPlayer(buildPlayerOptions);
```

## ⚠️ Pitfalls

- Do not symlink the root folder itself (`ln -s /source /target`); Unity canonicalizes root directory paths and will restore the spaced path.
- Always delete `Library/Bee` after changing stripping settings to ensure DAG caches do not re-trigger previous build failures.

## Verification

Run verification in batchmode:

```bash
/Applications/Unity/Hub/Editor/6000.6.0f1/Unity.app/Contents/MacOS/Unity -batchmode -nographics -projectPath "/path/without/spaces/UnityProject" -executeMethod MeenYsed.Editor.AutomatedVerticalSliceVerification.RunAllTests -quit -logFile /tmp/verify.log
```

Confirm 100% tests pass and standalone `.app` launches smoothly.
