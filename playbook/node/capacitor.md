---
tool: capacitor
scope: node
tier: optional
summary: "Bundled Capacitor iOS builds and a local iPhone install loop"
targets: ["capacitor.config.*", "Makefile", "package.json"]
detect: ["capacitor.config.*"]
---

# Capacitor iOS

## What

Capacitor packages an existing web app and its web assets in a native iOS app. Use this optional recipe when the app already uses Capacitor; it is not a requirement to convert web projects.

## Why

A bundled Release build lets you install and launch the app on a paired iPhone without a development server. A local install and [GitHub TestFlight delivery](testflight-github.md) are separate workflows.

## Config

On macOS, install an Xcode version compatible with the project's Capacitor release. Configure signing for the actual bundle ID and entitlements. Pair and trust the iPhone, and enable Developer Mode when requested.

**Protect local data before installing.** Sync or export unsynced data and retain the app's bundle and signing identity. Never uninstall the app or clear its storage to fix signing errors. Replacing a TestFlight install with a local install does not guarantee preservation of every local record. If replacement fails, stop and preserve the data before proceeding.

Set the app identity and static output in `capacitor.config.ts`. Replace `build` with the app's actual static build output directory.

```ts
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.example.myapp',
  appName: 'MyApp',
  webDir: 'build',
};

export default config;
```

Add a root `Makefile` target to build, sync, install, and launch. Keep the bundle ID consistent with the Capacitor config and the signed app.

```makefile
.PHONY: ios

IOS_DEVICE ?=
IOS_BUNDLE_ID ?= com.example.myapp

ios:
	@test -n "$(strip $(IOS_DEVICE))" || { echo 'Set IOS_DEVICE to a paired device name or identifier.' >&2; exit 1; }
	npm run build
	npx cap sync ios
	xcrun xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release -destination 'generic/platform=iOS' -derivedDataPath ios/DerivedData build
	xcrun devicectl device install app --device "$(IOS_DEVICE)" ios/DerivedData/Build/Products/Release-iphoneos/App.app
	xcrun devicectl device process launch --device "$(IOS_DEVICE)" "$(IOS_BUNDLE_ID)"
```

List paired devices and use an identifier if a name is missing or ambiguous.

```sh
xcrun devicectl list devices --timeout 10
```

Build, install, and launch on the selected iPhone.

```sh
make ios IOS_DEVICE="My iPhone"
```

## Gotchas

- Browser and shared-UI checks do not verify native APIs, signing, or physical-device behavior. Keep native-only calls behind the app's existing Capacitor adapter or plugin boundary.
- The native build bundles web assets. Publishing a new web build to Hosting does not update an installed app; rebuild and reinstall it.
- Check the standalone app on the iPhone: close Xcode, force-quit the app, and relaunch it from the home screen. Network-backed features may still require a network connection.
- WebView inspection is opt-in and is not a prerequisite for a Release install. Inspectability depends on the app's configuration.
- A local install does not verify TestFlight signing, upload, processing, or installation. Use the separate [GitHub TestFlight recipe](testflight-github.md) for distribution.
