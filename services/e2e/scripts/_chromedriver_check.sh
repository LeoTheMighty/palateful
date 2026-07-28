# shellcheck shell=bash
# Shared chromedriver preflight, sourced by e2e_lifecycle.sh and run_all.sh.
#
# A version mismatch is the expensive failure: `flutter drive` builds and
# boots the whole app, then dies on SessionNotCreatedException and buries
# the one useful line under a few thousand lines of stack trace plus a
# bogus "report this crash to Flutter" banner. ChromeDriver requires a
# matching MAJOR version with the Chrome it drives.
#
# Defines: check_chromedriver — returns 0 ok, 2 missing/mismatched.

check_chromedriver() {
  if ! command -v chromedriver >/dev/null 2>&1; then
    echo "ERROR: chromedriver not found on PATH." >&2
    echo "       See services/e2e/README.md for how to install a version-matched one." >&2
    return 2
  fi

  local chrome_bin="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
  # Can't locate Chrome (non-mac, custom install) — presence is all we can
  # assert, so don't block the run on a check we can't actually perform.
  [[ -x "$chrome_bin" ]] || return 0

  local chrome_version driver_version
  chrome_version="$("$chrome_bin" --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
  driver_version="$(chromedriver --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
  [[ -n "$chrome_version" && -n "$driver_version" ]] || return 0

  if [[ "${chrome_version%%.*}" != "${driver_version%%.*}" ]]; then
    echo "ERROR: chromedriver ${driver_version} cannot drive Chrome ${chrome_version}." >&2
    echo "       ChromeDriver must match Chrome's major version." >&2
    echo "       Get a matched build (the Homebrew cask is deprecated and lags):" >&2
    echo "         npx @puppeteer/browsers install chromedriver@${chrome_version}" >&2
    echo "       then put its directory first on PATH for the run." >&2
    return 2
  fi

  return 0
}
