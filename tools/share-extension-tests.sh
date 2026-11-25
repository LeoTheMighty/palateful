#!/bin/sh

# Unit tests for the iOS Share Extension's failure path (ifh-3).
#
# The extension has no XCTest target — adding one would mean booting a
# simulator on every CI run for logic that has no UIKit in it. Instead the
# pure-logic extension sources (no UIKit / SwiftUI) compile for the host
# platform with plain swiftc, and app/ios/PalatefulShareTests drives them.
#
# Run locally:   ./tools/share-extension-tests.sh
# Run in CI:     invoked from app/ios/ci_scripts/ci_post_clone.sh
#
# Requires the Xcode command-line tools (macOS only). On any other host the
# script exits 0 with a skip notice so a Linux CI job isn't broken by it.

set -e

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$REPO_ROOT/app/ios/PalatefulShare"
TESTS="$REPO_ROOT/app/ios/PalatefulShareTests"

if [ "$(uname)" != "Darwin" ] || ! command -v xcrun >/dev/null 2>&1; then
  echo "--- share-extension-tests: skipped (needs macOS + Xcode CLI tools) ---"
  exit 0
fi

BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

echo "--- share-extension-tests: building ---"
# Only the UIKit-free sources. ShareView / ShareViewController /
# ShareViewModel are iOS-only and aren't on the failure path under test.
xcrun swiftc -o "$BUILD_DIR/ShareExtensionTests" \
  "$SRC/SharedState.swift" \
  "$SRC/PendingImports.swift" \
  "$SRC/Telemetry.swift" \
  "$SRC/FailureNotifier.swift" \
  "$SRC/UploadService.swift" \
  "$TESTS/UploadServiceFailureTests.swift"

echo "--- share-extension-tests: running ---"
"$BUILD_DIR/ShareExtensionTests"
