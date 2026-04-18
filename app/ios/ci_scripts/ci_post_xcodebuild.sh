#!/bin/sh

# Xcode Cloud post-xcodebuild hook.
#
# Uploads dSYM files to Firebase Crashlytics after a successful archive
# so crash reports are symbolicated with human-readable stack traces.
#
# Xcode Cloud provides CI_ARCHIVE_PATH for archive actions.
# Runs only on archive (release) builds — skips for plain builds/tests.

set -e

if [ -z "$CI_ARCHIVE_PATH" ]; then
  echo "--- ci_post_xcodebuild: not an archive build, skipping dSYM upload ---"
  exit 0
fi

# Verify the Share Extension appex is embedded in the archived app wrapper.
# Apple archives sit at <CI_ARCHIVE_PATH>/Products/Applications/Runner.app.
# If the extension failed to embed, the share sheet entry won't appear even
# though the main app ships — catching this in CI beats catching it in TestFlight.
APP_WRAPPER="$CI_ARCHIVE_PATH/Products/Applications/Runner.app"
SHARE_APPEX="$APP_WRAPPER/PlugIns/PalatefulShare.appex"
if [ -d "$APP_WRAPPER" ]; then
  if [ ! -d "$SHARE_APPEX" ]; then
    echo "--- ci_post_xcodebuild: ERROR — PalatefulShare.appex not embedded at $SHARE_APPEX ---" >&2
    echo "--- Check that the Runner target's 'Embed App Extensions' phase lists PalatefulShare. ---" >&2
    exit 1
  fi
  echo "--- ci_post_xcodebuild: confirmed PalatefulShare.appex is embedded ---"
fi

DSYM_DIR="$CI_ARCHIVE_PATH/dSYMs"
UPLOAD_SYMBOLS="$CI_PRIMARY_REPOSITORY_PATH/app/ios/Pods/FirebaseCrashlytics/upload-symbols"
GSPLIST="$CI_PRIMARY_REPOSITORY_PATH/app/ios/Runner/GoogleService-Info.plist"

if [ ! -d "$DSYM_DIR" ]; then
  echo "--- ci_post_xcodebuild: no dSYMs directory found at $DSYM_DIR ---"
  exit 0
fi

if [ ! -x "$UPLOAD_SYMBOLS" ]; then
  echo "--- ci_post_xcodebuild: upload-symbols not found at $UPLOAD_SYMBOLS ---"
  exit 1
fi

echo "--- ci_post_xcodebuild: uploading dSYMs to Crashlytics ---"
"$UPLOAD_SYMBOLS" -gsp "$GSPLIST" -p ios "$DSYM_DIR"
echo "--- ci_post_xcodebuild: dSYM upload complete ---"
