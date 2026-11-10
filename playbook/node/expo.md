---
tool: expo
scope: node
tier: optional
summary: "Expo iOS development and standalone local iPhone builds"
targets: ["app.config.{js,ts}", "app.json", "package.json", "Makefile", "scripts/ios.sh"]
detect: ["app.config.{js,ts}"]
---

# Expo iOS

## What

Expo supports a development build with Metro and a separate standalone iOS Release build with embedded JavaScript. Use this optional recipe for an app that already uses Expo.

An `app.config.js` or `app.config.ts` file is a candidate marker, not proof of Expo. Confirm the `expo` dependency before applying this guidance. A project with only a static `app.json` is not auto-detected because that filename alone is not specific to Expo.

## Why

The development loop supports iteration with Metro. A standalone local install lets you check the bundled app on a paired iPhone without Metro running afterward. [GitHub TestFlight delivery](testflight-github.md) is a separate workflow.

## Config

On macOS, install an Xcode version compatible with the app's Expo SDK and install CocoaPods. Configure signing for the actual bundle ID and entitlements. Pair and trust the iPhone, and enable Developer Mode when requested. For routine wireless installs, keep the paired iPhone on the same Wi-Fi network as the Mac; device discovery and installation work while the screen is locked, and launching prompts the iPhone to unlock.

**Protect local data before installing.** Sync or export unsynced data and retain the app's bundle and signing identity. Never uninstall the app or clear its storage to fix signing errors. Replacing a TestFlight install with a local install does not guarantee preservation of every local record. If replacement fails, stop and preserve the data before proceeding.

Use `npx expo install <package>` to select SDK-compatible versions instead of independently pinning managed packages. For example, install the Expo development client:

```sh
npx expo install expo-dev-client
```

Use `npm run ios` when the app defines that script, or `npx expo run:ios`, to build and launch a simulator or development build. Run `npx expo start` to start Metro for an already installed compatible build. Use Expo Go only when it supports all of the app's native dependencies; custom native modules can require a development build.

For the following nested example, `frontend/` is the Expo app root. The workspace is `ios/MyApp.xcworkspace`, the scheme and executable are `MyApp`, the bundle ID is `com.example.myapp`, and derived data is `ios/DerivedData`. Replace the component path and app identities together with the actual project's values. Keep Expo config and plugins as the source of truth for generated native files.

Add a root `Makefile` target that passes an explicit device to the app-owned script.

```makefile
.PHONY: ios

IOS_DEVICE ?=
IOS_REUSE ?= 0

ios:
	IOS_REUSE="$(IOS_REUSE)" bash scripts/ios.sh "$(IOS_DEVICE)"
```

Create `scripts/ios.sh` at the repository root. A normal run rebuilds the standalone app; `IOS_REUSE=1` installs the existing build instead. Xcode's output goes to `ios/DerivedData/xcodebuild.log` and reaches the terminal only when the build fails, because the warnings in it come from Expo, React Native and CocoaPods generated code and cannot be fixed in the app.

```bash
#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
device="${1:-}"
if [[ -z "$device" ]]; then
  echo 'Set IOS_DEVICE to a paired device name or identifier.' >&2
  exit 1
fi

cd "$root/frontend"
app="ios/DerivedData/Build/Products/Release-iphoneos/MyApp.app"

if [[ "${IOS_REUSE:-0}" == 1 ]]; then
  if [[ ! -x "$app/MyApp" ]]; then
    echo 'No existing iOS build found. Run make ios first.' >&2
    exit 1
  fi
  echo 'Reusing the existing iOS build; source and configuration changes are not included.'
else
  export EXPO_NO_DOTENV=1
  if ! command -v pod >/dev/null 2>&1; then
    echo 'CocoaPods is required; install it and ensure pod is on PATH.' >&2
    exit 1
  fi
  npx expo prebuild --platform ios --no-install
  (cd ios && pod install)
  build_log="ios/DerivedData/xcodebuild.log"
  mkdir -p ios/DerivedData
  echo "Building the iOS app (log: frontend/$build_log)"
  if ! xcrun xcodebuild -quiet -workspace ios/MyApp.xcworkspace -scheme MyApp -configuration Release \
    -destination 'generic/platform=iOS' -derivedDataPath ios/DerivedData build >"$build_log" 2>&1; then
    { grep 'error: ' "$build_log" | grep -v 'exit code 0 but produced no further output' || true; tail -n 20 "$build_log"; } >&2
    echo "iOS build failed. Full log: frontend/$build_log" >&2
    exit 1
  fi
fi

xcrun devicectl list devices --timeout 10
xcrun devicectl device install app --device "$device" "$app"
xcrun devicectl device process launch --device "$device" "com.example.myapp"
```

The example sets `EXPO_NO_DOTENV=1`, so supply required app inputs through the command environment. Values named `EXPO_PUBLIC_*` are bundled public configuration, never secrets. Validate the app's required endpoint and OAuth configuration before native builds, using rules appropriate to that app.

List paired devices and use an identifier if a name is missing or ambiguous.

```sh
xcrun devicectl list devices --timeout 10
```

Build, install, and launch the standalone app on the selected iPhone.

```sh
make ios IOS_DEVICE="My iPhone"
```

To reinstall the existing build without incorporating source or configuration changes, run the reuse target.

```sh
make ios IOS_DEVICE="My iPhone" IOS_REUSE=1
```

## Gotchas

- Browser and shared-UI checks do not verify native modules, signing, or physical-device behavior. Keep native services in platform-specific modules when needed.
- Edit Expo config and plugins rather than generated native files. Do not use `prebuild --clean` as routine recovery.
- Check the standalone app on the iPhone: close Xcode and Metro, force-quit the app, and relaunch it from the home screen. Network-backed features may still require a network connection.
- A local install does not verify TestFlight signing, upload, processing, or installation. Use the separate [GitHub TestFlight recipe](testflight-github.md) for distribution.
- A failed build can print `error: the following command failed with exit code 0 but produced no further output`. It is a false Xcode message; the script filters it out, so look at the other `error:` lines.
