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

# Install Flutter from the stable channel into a cacheable path.
# CI_WORKSPACE is provided by Xcode Cloud and persists for the build.
git clone https://github.com/flutter/flutter.git --depth 1 -b stable "$HOME/flutter"
export PATH="$HOME/flutter/bin:$PATH"

flutter --version
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

echo "--- ci_post_clone: done ---"
