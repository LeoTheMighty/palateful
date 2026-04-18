# Android — Launch Runbook

> **Status (2026-04-18):** Stub. Paste-ready values live below;
> the full keystore/signing/Data Safety/tester-recruitment runbook
> lands under **epic-android-play-console-launch** stories
> `apl-1`–`apl-4`.
>
> This file exists today so the Palateful privacy policy epic
> (`epic-android-privacy-policy-page`) has a concrete cross-reference
> target and the two critical URL/email values have a single source of
> truth. Do **not** delete this file without updating
> `app/web/privacy.html` and the live Play Console fields listed below.

## Play Console Store Listing — paste-ready values

When filling the Play Console **Store Listing** and **Data Safety**
forms, use these exact values. They must match the content of
`app/web/privacy.html` — update both together or fail Play review.

| Play Console field          | Value                                       |
| --------------------------- | ------------------------------------------- |
| **Privacy Policy URL**      | `https://palateful.app/privacy`             |
| **Developer contact email** | `leonid@ac93.org`                           |

### Where these values must also be consistent

- `app/web/privacy.html` — the page itself at the URL above. The
  `mailto:` links must use the same contact email. Check with
  `grep -F leonid@ac93.org app/web/privacy.html` (expect 4+ matches).
- Play Console **Store Listing** → Privacy Policy URL field (pasted
  manually during apl-1 / apl-3).
- Play Console **Data Safety** form → the "Privacy policy" link field
  at the top of the form (same URL, same email in the developer
  contact block).
- iOS App Store Connect → App Privacy section (parallel field; same
  URL).

Changing the URL or email in any one of these places requires
simultaneous updates to all the others. Run
`grep -rF 'leonid@ac93.org' ANDROID.md app/web/privacy.html` as a
quick consistency check before shipping a change.

## Ownership

| Story                 | Owns                                                |
| --------------------- | --------------------------------------------------- |
| `app-1`               | `app/web/privacy.html` content + `_redirects`       |
| `app-2` (this file)   | The two paste-ready values above                    |
| `apl-1`               | Keystore generation + GitHub Secrets runbook        |
| `apl-2`               | Play Console store-listing graphics (icon / screens)|
| `apl-3`               | Data Safety paste blocks + permission justifications|
| `apl-4`               | Internal / closed-testing recruitment checklist     |

The `apl-*` stories will expand this file in place — keep the top
preamble and the paste-ready table; append everything else below.
