# Unity 6 iOS Physical Device Build: IL2CPP Compilation, DllImport Crash, and Code Signing Provisioning

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🔴 Critical                                |
| Last Verified | 2026-09-22                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `unity6`, `ios`, `il2cpp`, `xcode`, `codesign`, `provisioning_profile`, `devicectl`, `arm64`

---

## Problem

When exporting and building a Unity 6 (6000.6.0f1) project targeting physical iOS devices (`iOSSdkVersion.DeviceSDK`), developers encounter two sequential blockers:

1. **IL2CPP Segfault during Player Script Conversion:**
   The IL2CPP conversion tool crashes with `Segmentation fault: 11` (signal 11) inside `.NET TP Worker` / `ItemsWithMetadataIndexCollectorPhaseSortSupport` when scanning unmanaged P/Invoke methods or invalid `[DllImport("__Internal")]` declarations in `Assembly-CSharp.dll`.
2. **Missing Symbols during Xcode Linking:**
   `UnityFramework` fails to link with:
   ```
   Undefined symbols for architecture arm64:
     "InitIl2CppDefaults()", referenced from: il2cpp::vm::Runtime::Init in il2cpp.a
     "_g_CodegenRegistration", referenced from: il2cpp::vm::Runtime::Init in il2cpp.a
   ```
3. **Physical Installation Failure via devicectl:**
   ```
   ERROR: Unable to Install app (0xe8008015: A valid provisioning profile for this executable was not found.)
   ```

## Root Cause

1. **Invalid iOS Managed API Assumptions:**
   `UnityEngine.iOS.Device.thermalState` does not exist in standard Unity C# APIs. Attempting to bridge it with raw P/Invoke `[DllImport("__Internal")]` inside `Assembly-CSharp` can trigger an IL2CPP code generation bug during AST collection in Unity 6.
2. **Missing C++ Output Source Files:**
   When IL2CPP fails or partially exports, `Il2CppOutputProject/Source/il2cppOutput` lacks the generated C++ files (such as `Il2CppMetadataRegistration.cpp` and `Il2CppCodeRegistration.cpp`). Because these source files define the runtime codegen tables, linking `UnityFramework` against `libGameAssembly.a` fails.
3. **Apple Provisioning Profile Expiry:**
   Physical iOS devices strictly enforce an embedded provisioning profile (`embedded.mobileprovision`). If the Apple ID session stored in Xcode preferences has expired, automated signing (`-allowProvisioningUpdates`) fails with `Unable to log in with account ... login details were rejected`.

## Solution ✅

### 1. Remove Invalid APIs and Fragile DllImports
Avoid declaring ad-hoc P/Invoke `DllImport("__Internal")` inside core game assemblies unless accompanied by an explicit Xcode plugin framework. For performance profiling, use built-in `UnityEngine.SystemInfo` properties (`batteryLevel`, `batteryStatus`, `targetFrameRate`).

### 2. Verify IL2CPP C++ Source Synchronization
Ensure `Il2CppOutputProject/Source/il2cppOutput` contains the full set of generated C++ files (~470 files). Both `iOS_Simulator` and `iOS` targets share the same IL2CPP portable C++ code for ARM64:
```bash
cp -R Builds/iOS_Simulator/Il2CppOutputProject/Source/il2cppOutput/* Builds/iOS/Il2CppOutputProject/Source/il2cppOutput/
```

### 3. Compile UnityFramework and MainApp on External Volume
Compile using an external mounted disk (e.g. `/Volumes/XcodeDisk/DerivedData`) to prevent internal SSD exhaustion:
```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun xcodebuild \
  -project Builds/iOS/Unity-iPhone.xcodeproj \
  -scheme UnityFramework \
  -configuration ReleaseForRunning \
  -destination "generic/platform=iOS" \
  -derivedDataPath /Volumes/XcodeDisk/DerivedData \
  CODE_SIGNING_ALLOWED=NO build
```

### 4. Resolve Device Provisioning in Xcode GUI
When automated signing fails due to expired Apple credentials:
1. Open the project in Xcode GUI: `open -a Xcode Builds/iOS/Unity-iPhone.xcodeproj`.
2. Go to **Settings -> Accounts** and refresh the Apple ID login (enter 2FA code).
3. Under Target **Unity-iPhone -> Signing & Capabilities**, let Xcode automatically generate the development profile for the bundle ID.
4. Install directly via Xcode Run button or via CLI:
```bash
xcrun devicectl device install app --device "<UDID>" /Volumes/XcodeDisk/DerivedData/Build/Products/ReleaseForRunning-iphoneos/MeenYsed-.app
```
