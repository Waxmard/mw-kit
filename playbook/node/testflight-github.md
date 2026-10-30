---
tool: testflight-github
scope: node
tier: optional
summary: "Separate GitHub Actions signing, archive, and TestFlight upload workflow"
targets: [".github/workflows/deploy-testflight.yml", "scripts/build-ios-testflight.sh"]
detect: ["capacitor.config.*", "app.config.{js,ts}", ".github/workflows/deploy-testflight.yml"]
platform: github
---

# TestFlight delivery with GitHub Actions

## What

This optional recipe signs, archives, exports, and uploads an iOS app to TestFlight from GitHub Actions. It complements the local [Capacitor](capacitor.md) and [Expo](expo.md) device recipes. A missing workflow is an optional suggestion, not a defect.

## Why

A dedicated distribution workflow keeps signing and upload separate from local device builds. Creating this playbook does not enable a consumer workflow. Enabling the `main` push trigger below opts into distribution on every push to that branch.

## Config

Register the Apple app, bundle ID, team, and capabilities before using the workflow. Configure automatic signing and an App Store Connect API key with upload access. Every extension needs its own matching bundle identity, entitlements, and signing configuration. Select a GitHub macOS runner and Xcode version compatible with the app's SDK.

Store `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY`, `APPLE_CERTIFICATE_P12_BASE64`, and `APPLE_CERTIFICATE_PASSWORD` in the GitHub `preview` environment's secrets. Set `APPLE_TEAM_ID` and `IOS_BUNDLE_ID` as repository or environment variables for the existing app. Keep public app build inputs in environment variables or repository variables; keep credentials in environment secrets. Values named `EXPO_PUBLIC_*` are bundled public configuration, not secrets.

Add `.github/workflows/deploy-testflight.yml` for a root app. The example public API URL is an app-specific input; replace or remove it and supply the public inputs that your app actually requires.

```yaml
name: Deploy TestFlight

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: deploy-testflight-main
  cancel-in-progress: false

jobs:
  deploy-ios-testflight:
    runs-on: macos-latest
    environment: preview
    steps:
      - uses: actions/checkout@v7
      - uses: jdx/mise-action@v4
      - name: Install dependencies
        run: npm ci
      - name: Archive and upload
        run: bash scripts/build-ios-testflight.sh
        env:
          APPLE_TEAM_ID: ${{ vars.APPLE_TEAM_ID }}
          IOS_BUNDLE_ID: ${{ vars.IOS_BUNDLE_ID }}
          IOS_BUILD_NUMBER: ${{ github.run_number }}.${{ github.run_attempt }}
          EXPO_PUBLIC_API_URL: ${{ vars.EXPO_PUBLIC_API_URL }}
          ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
          APPLE_CERTIFICATE_P12_BASE64: ${{ secrets.APPLE_CERTIFICATE_P12_BASE64 }}
          APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
```

For the nested Expo example, replace the dependency-install step with this one. Install dependencies only at the location appropriate to the app. Use `npm ci` without universally suppressing lifecycle scripts: some apps need their postinstall patches.

```yaml
      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci
```

The following ordered shell blocks form one consumer-owned `scripts/build-ios-testflight.sh`, not separate shell sessions. Copy the first block, exactly one preparation block, and the final common block in that order. The first block uses the repository root as the app root; for the nested Expo example, change `APP_DIR="$ROOT"` to `APP_DIR="$ROOT/frontend"`. Use the app's existing team and bundle identity, and set an explicit build number for standalone script runs.

Start the script by validating the required inputs and the version from the selected app's `package.json`. Validation happens before native preparation.

```bash
#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT"
missing=''
for name in APPLE_TEAM_ID IOS_BUNDLE_ID IOS_BUILD_NUMBER ASC_KEY_ID ASC_ISSUER_ID ASC_PRIVATE_KEY APPLE_CERTIFICATE_P12_BASE64 APPLE_CERTIFICATE_PASSWORD; do
  if [[ -z "${!name:-}" ]]; then
    missing="$missing $name"
  fi
done
if [[ -n "$missing" ]]; then
  printf 'Missing required environment variable(s):%s\n' "$missing" >&2
  exit 1
fi

MARKETING_VERSION="$(node -p 'require(process.argv[1]).version' "$APP_DIR/package.json")"
if [[ ! "$MARKETING_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Invalid MARKETING_VERSION: %s\n' "$MARKETING_VERSION" >&2
  exit 1
fi
if [[ ! "$IOS_BUILD_NUMBER" =~ ^[0-9]+(\.[0-9]+){0,2}$ ]]; then
  printf 'Invalid IOS_BUILD_NUMBER: %s\n' "$IOS_BUILD_NUMBER" >&2
  exit 1
fi
```

For Capacitor, use the production web build and sync its bundled assets into the existing native project. Replace the example project, scheme, and product together if the app uses different names.

```bash
cd "$APP_DIR"
npm run build
npx cap sync ios
xcode_container=(-project ios/App/App.xcodeproj)
SCHEME=App
PRODUCT=App
```

For Expo, select `frontend/` as described above, supply the app's required public build inputs through the command environment, and validate its required endpoint and OAuth configuration before native preparation. The example disables dotenv loading. Keep Expo config and plugins as the source of truth, and replace the workspace, scheme, and product together with the app's actual names.

```bash
cd "$APP_DIR"
export EXPO_NO_DOTENV=1
if ! command -v pod >/dev/null 2>&1; then
  echo 'CocoaPods is required; install it and ensure pod is on PATH.' >&2
  exit 1
fi
npx expo prebuild --platform ios --no-install
(cd ios && pod install)
xcode_container=(-workspace ios/MyApp.xcworkspace)
SCHEME=MyApp
PRODUCT=MyApp
```

Finish the same script with the common signing, archive, export, and upload steps. The temporary keychain search list is restored and temporary files are removed on exit. Do not enable shell tracing or print private values.

```bash
umask 077
WORK_DIR="$(mktemp -d "${RUNNER_TEMP:-/tmp}/ios-testflight.XXXXXX")"
KEYCHAIN_PATH="$WORK_DIR/build.keychain-db"
existing_keychains=()
restore_keychains=0
cleanup() {
  if [[ "$restore_keychains" == 1 ]]; then
    security list-keychains -d user -s ${existing_keychains[@]+"${existing_keychains[@]}"} >/dev/null 2>&1 || echo 'Could not restore the keychain search list.' >&2
  fi
  security delete-keychain "$KEYCHAIN_PATH" >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

keychain_list="$(security list-keychains -d user)"
while IFS= read -r line; do
  trimmed="${line#"${line%%[![:space:]]*}"}"
  trimmed="${trimmed%\"}"
  trimmed="${trimmed#\"}"
  if [[ -n "$trimmed" ]]; then
    existing_keychains+=("$trimmed")
  fi
done <<< "$keychain_list"

KEYCHAIN_PASSWORD="$(openssl rand -hex 24)"
printf '%s' "$APPLE_CERTIFICATE_P12_BASE64" | base64 --decode >"$WORK_DIR/dist.p12"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
restore_keychains=1
security list-keychains -d user -s "$KEYCHAIN_PATH" ${existing_keychains[@]+"${existing_keychains[@]}"}
security import "$WORK_DIR/dist.p12" -k "$KEYCHAIN_PATH" -P "$APPLE_CERTIFICATE_PASSWORD" -T /usr/bin/codesign -t cert -f pkcs12
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"

AUTH_KEY_PATH="$WORK_DIR/AuthKey_${ASC_KEY_ID}.p8"
printf '%s\n' "$ASC_PRIVATE_KEY" >"$AUTH_KEY_PATH"
EXPORT_OPTIONS_PLIST="$WORK_DIR/ExportOptions.plist"
cat >"$EXPORT_OPTIONS_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>destination</key>
  <string>export</string>
  <key>manageAppVersionAndBuildNumber</key>
  <false/>
  <key>method</key>
  <string>app-store-connect</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>teamID</key>
  <string>${APPLE_TEAM_ID}</string>
</dict>
</plist>
EOF

ARCHIVE_PATH="$WORK_DIR/$PRODUCT.xcarchive"
EXPORT_PATH="$WORK_DIR/export"
xcrun xcodebuild \
  "${xcode_container[@]}" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE_PATH" \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \
  MARKETING_VERSION="$MARKETING_VERSION" \
  CURRENT_PROJECT_VERSION="$IOS_BUILD_NUMBER" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$AUTH_KEY_PATH" \
  -authenticationKeyID "$ASC_KEY_ID" \
  -authenticationKeyIssuerID "$ASC_ISSUER_ID" \
  archive

archive_bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :ApplicationProperties:CFBundleIdentifier' "$ARCHIVE_PATH/Info.plist")"
if [[ "$archive_bundle_id" != "$IOS_BUNDLE_ID" ]]; then
  printf 'Archive bundle ID %s does not match IOS_BUNDLE_ID %s\n' "$archive_bundle_id" "$IOS_BUNDLE_ID" >&2
  exit 1
fi

xcrun xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS_PLIST" \
  -exportPath "$EXPORT_PATH" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$AUTH_KEY_PATH" \
  -authenticationKeyID "$ASC_KEY_ID" \
  -authenticationKeyIssuerID "$ASC_ISSUER_ID"

IPA_PATH="$EXPORT_PATH/$PRODUCT.ipa"
if [[ ! -f "$IPA_PATH" ]]; then
  printf 'Expected exported IPA not found: %s\n' "$IPA_PATH" >&2
  exit 1
fi
API_PRIVATE_KEYS_DIR="$WORK_DIR" xcrun altool \
  --upload-app \
  -f "$IPA_PATH" \
  --type ios \
  --apiKey "$ASC_KEY_ID" \
  --apiIssuer "$ASC_ISSUER_ID"
```

## Gotchas

- The archive uses the project's existing bundle settings and checks the app's archived bundle ID against `IOS_BUNDLE_ID`. It does not override extension bundle IDs.
- GitHub run and attempt numbers are not globally unique across unrelated workflows. Ensure each build number advances the app's previous build number in App Store Connect.
- The upload command follows the inspected app workflows. Confirm that the selected Xcode toolchain still supports `xcrun altool` before relying on it.
- Upload success does not prove that TestFlight processing or installation succeeded. Check both separately in App Store Connect and on a device.
