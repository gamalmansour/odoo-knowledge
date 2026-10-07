# Flutter iOS Physical Device Discovery and Direct Deployment via Xcode devicectl

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | deployment                                 |
| Odoo Versions | All (Mobile Client)                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-07                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `flutter`, `ios`, `xcode`, `devicectl`, `deployment`, `mobile`

---

## Problem

When connecting an iPhone via USB or Wi-Fi to a Mac developer workstation, `flutter devices` reports only `macOS` and `Chrome`, failing to detect the physical iOS device even though the iPhone is paired, trusted, and visible in Finder.

```
Found 2 connected devices:
  macOS (desktop) • macos  • darwin-arm64
  Chrome (web)    • chrome • web-javascript
No wireless devices were found.
```

Furthermore, attempting to run `xcrun devicectl list devices` returns:
```
xcrun: error: unable to find utility "devicectl", not a developer tool or in PATH
```

## Root Cause

`xcode-select -p` is pointed by default to `/Library/Developer/CommandLineTools` rather than the complete Xcode IDE application directory at `/Applications/Xcode.app/Contents/Developer`. Modern iOS (iOS 17+) requires Apple's `devicectl` utility (introduced in Xcode 15+), which resides solely inside the Xcode application bundle.

## Solution ✅

### 1. Export DEVELOPER_DIR to Xcode Path
Override the developer directory environment variable in the execution context:

```bash
export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"
```

Verify device visibility:
```bash
$DEVELOPER_DIR/usr/bin/xcrun devicectl list devices
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer flutter devices
```

### 2. Build and Sign the iOS App for Physical Hardware
Compile the Flutter runner with the active development team ID:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer flutter build ios --debug
```

### 3. Deploy and Launch via devicectl without Xcode GUI Overhead
Install the `.app` directly to the target device UDID:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device install app \
  --device <DEVICE_UDID> \
  build/ios/iphoneos/Runner.app

# Immediately launch on device:
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device process launch \
  --device <DEVICE_UDID> \
  com.yourcompany.app
```

## ⚠️ Pitfalls

- **Developer Mode on iOS:** Ensure `Settings > Privacy & Security > Developer Mode` is toggled ON on the physical iPhone and the phone has been rebooted once after enabling.
- **VPN / WireGuard conflicts:** If deploying over local Wi-Fi, ensure corporate VPNs do not block local multicast DNS (mDNS) discovery.

## Verification

Run:
```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl list devices
```
Confirm the device state shows `available (paired)` and the app launches smoothly on the screen.
