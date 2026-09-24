# Unity 6 iOS Physical Device Build: IL2CPP Compilation, DllImport Crash, and Code Signing Provisioning

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-25                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity6`, `ios`, `il2cpp`, `xcode`, `codesign`, `provisioning_profile`, `devicectl`, `arm64`, `exfat`, `burst`, `nativeaot`

---

## Problem

When exporting and building a Unity 6 (6000.6.0f1) project targeting physical iOS devices (`iOSSdkVersion.DeviceSDK`), developers encounter four sequential blockers:

1. **IL2CPP Segfault during Player Script Conversion (macOS 26 / Darwin 25):**
   The IL2CPP standalone converter crashes with `Fatal error. System.AccessViolationException` or `SIGSEGV` (signal 11) in `_sigtramp` / `GCHeap::GarbageCollect` due to .NET 8 / NativeAOT multithreaded Server GC thread suspension signals on Apple Silicon.
2. **ExFAT AppleDouble Copy Crash in BeeBuildPostprocessor:**
   When the project is hosted on an external ExFAT SSD, macOS creates AppleDouble (`._*`) resource fork shadow files in `Temp/BurstOutput/`. During iOS build postprocessing, Unity's `BeeBuildPostprocessor.GenerateNativePluginsForAssemblies` attempts to copy the Burst static library folder and throws:
   ```
   System.ArgumentException: Copy() called on path that doesnt exist: Temp/BurstOutput/DebugInformation/StaticLibraries/._lib_burst_generated.txt
     at NiceIO.NPath.CopyWithDeterminedDestination ...
     at UnityEditor.Modules.BeeBuildPostprocessor.GenerateNativePluginsForAssemblies ...
   ```
3. **Missing Symbols during Xcode Linking:**
   `UnityFramework` fails to link if `Il2CppOutputProject/Source/il2cppOutput` C++ files are missing or incomplete.
4. **Physical Device Launch Security Denial:**
   ```
   ERROR: Unable to launch com.meenysed.game because it has an invalid code signature, inadequate entitlements or its profile has not been explicitly trusted by the user. (FBSOpenApplicationErrorDomain error 3)
   ```

## Root Cause

1. **NativeAOT Server GC on Darwin 25:**
   The .NET 8 NativeAOT runtime bundled with Unity 6 IL2CPP defaults to multithreaded Server GC (`gcServer=1`), which issues thread suspension signals that conflict with Darwin 25 kernel thread scheduling on Apple Silicon.
2. **ExFAT VFS Extended Attributes Lack Native Support:**
   ExFAT does not natively support Darwin extended attributes (xattr). The macOS kernel automatically creates AppleDouble `._*` companion files. Unity's `NiceIO.NPath` directory copy enumerates these files but standard filesystem APIs fail to open them as regular files.
3. **First-Time Developer Profile Trust on iOS:**
   Physical iOS devices require explicit user authorization for Free/Personal Developer team certificates before SpringBoard allows process launch.

## Solution ✅

### 1. Fix IL2CPP NativeAOT Server GC Crash
Export the following environment variables before invoking Unity batchmode or IL2CPP:
```bash
export DOTNET_gcServer=0
export DOTNET_gcConcurrent=0
export DOTNET_GCHeapHardLimit=0x200000000
export COMPlus_gcServer=0
export COMPlus_gcConcurrent=0
```

### 2. Suppress Burst AOT & Clean AppleDouble Files on ExFAT
1. Disable Burst AOT compilation for iOS by creating `ProjectSettings/BurstAotSettings_iOS.json` and `ProjectSettings/CommonBurstAotSettings.json`:
   ```json
   {
     "MonoBehaviour": {
       "Version": 5,
       "EnableBurstCompilation": false,
       "EnableOptimisations": false,
       "EnableSafetyChecks": false,
       "EnableDebugInAllBuilds": false,
       "UsePlatformSDKLinker": false,
       "EnableArmv9SecurityFeatures": false
     }
   }
   ```
2. Set `export COPYFILE_DISABLE=1`.
3. In custom C# build scripts, run a background thread during `BuildPipeline.BuildPlayer` that purges any `._*` files created in `Temp/`.

### 3. Archive & Package IPA via Xcode CLI
```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project Builds/iOS/Unity-iPhone.xcodeproj \
  -scheme Unity-iPhone \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath Builds/iOS/MeenYsed.xcarchive archive -allowProvisioningUpdates

# Package into IPA
mkdir -p /tmp/ipa/Payload
cp -R Builds/iOS/MeenYsed.xcarchive/Products/Applications/MeenYsed-.app /tmp/ipa/Payload/
cd /tmp/ipa && zip -qr MeenYsed_Release.ipa Payload
```

### 4. Install & Authorize on Physical iOS Device
1. Install via `devicectl`:
   ```bash
   DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device install app --device "<UDID>" MeenYsed_Release.ipa
   ```
2. On the physical iPhone:
   Navigate to **Settings (الإعدادات) → General (عام) → VPN & Device Management (إدارة VPN والجهاز) → Developer App (`<Developer Email>`) → Trust (الوثوق في المطور)**.
3. Once trusted, launch via `devicectl` or tap the icon directly on the home screen:
   ```bash
   DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device process launch --device "<UDID>" com.meenysed.game
   ```
