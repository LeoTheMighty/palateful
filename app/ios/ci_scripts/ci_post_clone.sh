#!/bin/sh

# Xcode Cloud post-clone hook.
#
# Xcode Cloud doesn't know this is a Flutter project, so it never runs
# `flutter pub get` or `pod install` before handing off to xcodebuild.
# Without this script the Release build fails on missing
# Flutter/Generated.xcconfig and missing Pods xcfilelists.
#
# This runs once after the repo is cloned, before xcodebuild starts.
# Apple requires the script to live in `ci_scripts/` adjacent to the
# .xcworkspace — i.e. app/ios/ci_scripts/ here.

set -e

echo "--- ci_post_clone: installing Flutter ---"

# Install Flutter at the repo's PINNED version into a cacheable path.
# CI_WORKSPACE is provided by Xcode Cloud and persists for the build.
#
# tfship1 (2026-09-20): this used to be `-b stable`, i.e. the *tip* of the
# stable channel. That matched the pin when this hook was written on
# 2026-04-15 and silently drifted apart every Flutter release since — by
# 2026-09-20 the tip was 3.47.5 against a repo pinned at 3.41.7, six minor
# versions. Nothing reported it because nothing compares them.
#
# Keep FLUTTER_VERSION in step with .github/workflows/ci.yml (flutter-test)
# and mobile-builds.yml. Bumping Flutter means changing all of them in one
# PR — see the note in mobile-builds.yml for why.
FLUTTER_VERSION="3.41.7"

# Clone the tag shallowly, then put a branch named `stable` on it. The branch
# name is load-bearing: Flutter derives its channel from it, so a plain
# detached checkout of the tag reports channel "unknown".
git clone https://github.com/flutter/flutter.git --depth 1 -b "$FLUTTER_VERSION" "$HOME/flutter"
git -C "$HOME/flutter" checkout -b stable
export PATH="$HOME/flutter/bin:$PATH"

flutter --version

# Fail loudly rather than building against a version nothing has tested.
# A silent mismatch is the failure mode this pin exists to prevent.
if ! flutter --version | grep -q "Flutter $FLUTTER_VERSION "; then
  echo "--- ERROR: expected Flutter $FLUTTER_VERSION, got: ---" >&2
  flutter --version >&2
  exit 1
fi

flutter precache --ios

echo "--- ci_post_clone: flutter pub get ---"
cd "$CI_PRIMARY_REPOSITORY_PATH/app"
flutter pub get

echo "--- ci_post_clone: pod install ---"
cd "$CI_PRIMARY_REPOSITORY_PATH/app/ios"
pod install

# Lint the Share Extension for memory-footgun patterns (sie-4 AC).
# The 80 MB RSS ceiling relies on streaming PUTs from file; any of these
# patterns would buffer the full payload in extension memory and blow
# the 120 MB iOS extension process limit on a 100 MB video share.
echo "--- ci_post_clone: sie-4 memory-footgun lint ---"
PSS_DIR="$CI_PRIMARY_REPOSITORY_PATH/app/ios/PalatefulShare"
if [ -d "$PSS_DIR" ]; then
  if grep -RInE 'Data\(contentsOf:|UIImage\(data:|UIImage\(contentsOfFile:' "$PSS_DIR"; then
    echo "--- ERROR: forbidden buffered-read pattern in PalatefulShare/ — use uploadTask(with:fromFile:) instead ---" >&2
    exit 1
  fi
fi

# Share Extension failure-path unit tests (ifh-3 AC). The extension has no
# XCTest target; these compile the UIKit-free sources for the host and run
# them directly, so they cost seconds and no simulator boot.
echo "--- ci_post_clone: share extension unit tests ---"
sh "$CI_PRIMARY_REPOSITORY_PATH/tools/share-extension-tests.sh"

echo "--- ci_post_clone: done ---"
