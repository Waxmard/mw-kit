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

A dedicated distribution workflow keeps signing and upload separate from local device builds. Ordinary pushes run checks and release discovery, not TestFlight uploads. Creating this playbook does not enable a consumer workflow.

## Config

Register the Apple app, bundle ID, team, and capabilities before using the workflow. Configure automatic signing and an App Store Connect API key with upload access. Every extension needs its own matching bundle identity, entitlements, and signing configuration. Select a GitHub macOS runner and Xcode version compatible with the app's SDK.

This recipe assumes automatic signing with a Release archive that uses an Apple Development identity, followed by an App Store Connect export using a distribution identity. Other signing configurations may not need both identities. Reuse existing certificates and their private keys rather than creating new certificates to work around quota failures.

Store `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_DEVELOPMENT_CERTIFICATE_P12_BASE64`, and `APPLE_DEVELOPMENT_CERTIFICATE_PASSWORD` in the GitHub `preview` environment's secrets. Set `APPLE_TEAM_ID` and `IOS_BUNDLE_ID` as repository or environment variables for the existing app. Keep public app build inputs in environment variables or repository variables; keep credentials in environment secrets. Values named `EXPO_PUBLIC_*` are bundled public configuration, not secrets.

Add `.github/workflows/deploy-testflight.yml` for a root app. The example public API URL is an app-specific input; replace or remove it and supply the public inputs that your app actually requires.

```yaml
name: Deploy TestFlight

on:
  release:
    types: [published]
  workflow_dispatch: {}

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
        with:
          ref: ${{ github.event_name == 'release' && github.event.release.tag_name || github.sha }}
      - uses: jdx/mise-action@v5
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
          APPLE_DEVELOPMENT_CERTIFICATE_P12_BASE64: ${{ secrets.APPLE_DEVELOPMENT_CERTIFICATE_P12_BASE64 }}
          APPLE_DEVELOPMENT_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_DEVELOPMENT_CERTIFICATE_PASSWORD }}
```

Release runs build the published tag. Manual runs build the commit captured for the selected ref when the run started, even if its branch advances. The explicit fallback uses `github.sha` because an explicit ref bypasses checkout's [automatic event-commit pinning](https://github.com/actions/checkout/blob/main/src/input-helper.ts).

Delivery does not wait for continuous integration (CI). Retain the repository's required checks and release controls.

For the nested Expo example, replace the dependency-install step with this one. Install dependencies only at the location appropriate to the app. Use `npm ci` without universally suppressing lifecycle scripts: some apps need their postinstall patches.

```yaml
      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci
```

The following ordered shell blocks form one consumer-owned `scripts/build-ios-testflight.sh`, not separate shell sessions. Copy the first block, exactly one preparation block, and the final common block in that order. The first block uses the repository root as the app root; for the nested Expo example, change `APP_DIR="$ROOT"` to `APP_DIR="$ROOT/frontend"`. Use the app's existing team and bundle identity, and set an explicit build number for standalone script runs.

Start the script by validating the required inputs and version, then set up the temporary keychain and check the development identity. These steps happen before native preparation. The keychain search list is restored and temporary files are removed on exit. Do not enable shell tracing or print private values.

```bash
#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT"
missing=''
for name in APPLE_TEAM_ID IOS_BUNDLE_ID IOS_BUILD_NUMBER ASC_KEY_ID ASC_ISSUER_ID ASC_PRIVATE_KEY APPLE_CERTIFICATE_P12_BASE64 APPLE_CERTIFICATE_PASSWORD APPLE_DEVELOPMENT_CERTIFICATE_P12_BASE64 APPLE_DEVELOPMENT_CERTIFICATE_PASSWORD; do
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
printf '%s' "$APPLE_DEVELOPMENT_CERTIFICATE_P12_BASE64" | base64 --decode >"$WORK_DIR/development.p12"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
restore_keychains=1
security list-keychains -d user -s "$KEYCHAIN_PATH" ${existing_keychains[@]+"${existing_keychains[@]}"}
security import "$WORK_DIR/dist.p12" -k "$KEYCHAIN_PATH" -P "$APPLE_CERTIFICATE_PASSWORD" -T /usr/bin/codesign -t cert -f pkcs12
security import "$WORK_DIR/development.p12" -k "$KEYCHAIN_PATH" -P "$APPLE_DEVELOPMENT_CERTIFICATE_PASSWORD" -T /usr/bin/codesign -t cert -f pkcs12
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"

identities="$(security find-identity -v -p codesigning "$KEYCHAIN_PATH")"
if [[ ! "$identities" =~ \"(Apple\ Development|iPhone\ Developer):\  ]]; then
  echo 'No valid Apple Development signing identity in the build keychain; supply an existing development certificate with its private key.' >&2
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

Finish the same script with the App Store Connect API key, archive, export, and upload steps.

```bash
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

## Capacitor-only Linux build

To build the web app on Linux and sign on macOS, modify the canonical workflow and replace the Capacitor preparation block below. Keep the single-job workflow and its original preparation block for Expo.

Add this job under `jobs` alongside `deploy-ios-testflight`. Supply the app's public build inputs here because they are bundled into the artifact. Move the example `EXPO_PUBLIC_API_URL` from the archive step to this build step, replacing or removing it for the app's actual inputs.

```yaml
  build-app:
    runs-on: ubuntu-latest
    environment: preview
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event_name == 'release' && github.event.release.tag_name || github.sha }}
      - uses: jdx/mise-action@v5
      - run: npm ci
      - run: npm run build
        env:
          EXPO_PUBLIC_API_URL: ${{ vars.EXPO_PUBLIC_API_URL }}
      - uses: actions/upload-artifact@v7
        with:
          name: web-build-${{ github.run_id }}-${{ github.run_attempt }}
          path: build
          if-no-files-found: error
          retention-days: 1
```

Add `needs: build-app` to the existing signing job, retaining its other settings and steps.

```yaml
  deploy-ios-testflight:
    needs: build-app
```

After its dependency install and before the archive step, download the artifact into `build`.

```yaml
      - uses: actions/download-artifact@v8
        with:
          name: web-build-${{ github.run_id }}-${{ github.run_attempt }}
          path: build
```

The signing job waits for the build job; a failed build or missing artifact stops delivery rather than rebuilding on macOS. Always install dependencies before downloading the artifact.

Replace the single-job Capacitor preparation block in the script with this block. It syncs the artifact without rebuilding it.

```bash
cd "$APP_DIR"
npx cap sync ios
xcode_container=(-project ios/App/App.xcodeproj)
SCHEME=App
PRODUCT=App
```

Use `npm ci --ignore-scripts` on macOS only after inspecting the app's dependency tree and verifying no dependency needs lifecycle builds. Keep `npm ci` as the safe default, especially for Expo.

After any failure or artifact expiration, choose **Re-run all jobs**. Do not choose **Re-run failed jobs**: the incremented `github.run_attempt` can make macOS look for an artifact that the successful Linux job did not rebuild. See GitHub's documentation on [rerunning workflows and jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs) and [default variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).

## Gotchas

- The archive uses the project's existing bundle settings and checks the app's archived bundle ID against `IOS_BUNDLE_ID`. It does not override extension bundle IDs.
- GitHub run and attempt numbers are not globally unique across unrelated workflows. Ensure each build number advances the app's previous build number in App Store Connect.
- The upload command follows the inspected app workflows. Confirm that the selected Xcode toolchain still supports `xcrun altool` before relying on it.
- Upload success does not prove that TestFlight processing or installation succeeded. Check both separately in App Store Connect and on a device.
