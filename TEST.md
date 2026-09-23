What to test next:
* Share to app capabilities
    * URL from friend
    * Picture from anywhere
    * Tik Tok video
    * Youtube
    * Instagram Post ?
* Cooking mode
## Filed by /devx (2026-07-27)

- [ ] `test/test-hmpseed-2026-07-27T19:05-hmp5-flow-always-skips-in-e2e.md` — the hmp-5 e2e flow (`08_meals_home_promotion_test.dart`) self-skips: it needs ≥2 recipes on the home grid, and nothing seeds the e2e `test` DB, so it reports as passed-by-skip and its contract-drift protection never runs. Status: ready. From: bqa102.

## Filed by /devx (2026-09-22)

- [ ] `test/test-scanmig1-2026-09-22T20:30-feature-services-onto-brace-scanner.md` — the feature-services section of the silent-catch guard still uses the 40-line window, which passes catches that swallow (measured: `shopping_cart_service.dart:358` passes on a report 30 lines below, in another method). Migrate it onto the brace-matched scanner authrep1 added for `app/lib/core`. Status: ready. From: authrep1.
