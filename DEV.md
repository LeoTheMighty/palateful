MANUAL DOCS:
- [ ] ANDROID.md
- [ ] SHARE.md

Next devs:
- [x] /dev epic-bugs-home-polish
- [x] /dev epic-notifications-ios-proofoflife
- [x] /dev epic-bugs-import-structured-ingredients
- [x] /dev epic-bugs-import-photo-pipeline
- [x] /dev epic-calendars-foundation 
        ->
- [x] /dev epic-calendars-sharing 

- [x] /dev epic-observability-latency    
- [x] /dev epic-user-feedback 

- [x] /dev epic-activity-hub-redesign # foundation: two-tab shell + swipe + See-all
- [...] /dev epic-import-row-rich-detail   # caret expansion + confidence + telemetry     (blocked by above)          

- [x] /dev epic-review-import-ingredient-polish # independent — can start in parallel with either of the above 

  - [x] /dev epic-share-backend-foundations   # backend, no dependencies
  - [x] /dev epic-share-android-entrypoint    # can run in parallel with backend; unblocks Android
  - [x] /dev epic-share-receiving-ux # depends on backend + Android
  - [x] /dev epic-share-ios-extension  # depends on backend; longest pole — consider starting in parallel with receiving-ux once backend lands

  Android
- [x] /dev epic-android-privacy-policy-page # ships first — unblocks everything downstream
- [x] /dev epic-android-release-hardening # app-layer prep (can run in parallel with ci-hardening once privacy is live)            
- [x] /dev epic-android-ci-hardening # CI prep; depends  on arh-5 landing for Gradle-side Crashlytics config               
- [x] /dev epic-android-play-console-launch # terminal epic — docs + store assets, plus the human Play Console runbook 

Push Notifs
- [x] /dev epic-notifications-push-diagnostics-hardening  

Meal Grouping:
- [x] /dev epic-meals-create-and-view # foundation — run first
- [x] /dev epic-meals-discoverability # parallelizable after foundation
- [x] /dev epic-meals-calendar  # parallelizable after foundation
- [x] /dev epic-meals-sharing-and-ai # parallelizable after foundation (msa-4 soft-depends on calendar)

Calendar Per Meal Shopping Cart Add:
- [x] /dev epic-calendar-per-meal-shopping-add

Cook Mode:
- [x] /dev epic-cook-mode-polish # Flutter-only, can start now        
- [x] /dev epic-cook-mode-timers # Full-stack, independent — can run in parallel

Activity Hub:
- [x] /dev epic-activity-badge-integrity
- [x] /dev epic-activity-full-history # depends on epic-activity-badge-integrity  

Refactor Ingredients:
- [x] /dev epic-ingredients-string-simplification 

Extractor Refine:
- [x] /dev epic-extractor-field-inference

Meal UI Refine:
- [x]  /dev epic-meals-home-promotion

Performance:
  # First — the foundation.  pim-1 is a hard gate for  capturing before-numbers
  # on the other stories in this epic.              
- [x] /dev epic-perf-infra-and-measurement                
   
  # Then — the two siblings can run in parallel (different surfaces):     
- [x] /dev epic-perf-backend-query-tuning
- [x] /dev epic-perf-flutter-client-polish

Notification Improvements:
- [x] /dev epic-notifications-foundation-prefs-copy       
- [x] /dev epic-notifications-meal-reminders              # depends on      foundation
- [x] /dev epic-notifications-timer-actions-live-activities # depends on foundation  
- [x] /dev epic-notifications-partner-activity # depends on foundation
- [x] /dev epic-notifications-scheduled-reminders # depends on foundation

Reactivity:
- [x] /dev epic-reactive-foundation-home-imports      
- [x] /dev epic-reactive-migration-meals-calendar     #      parallelizable with next; depends on foundation
- [x] /dev epic-reactive-migration-books-profile-pantry-and-polish #     parallelizable with prev; depends on foundation

Meal Cook Mode:
- [ ] /dev epic-cook-mode-remove-chat                   
- [ ] /dev epic-cook-mode-resume    # soft-depends on   chat-removal (header     layout)                
- [ ] /dev epic-cook-mode-meal # hard-depends on resume (CookSessionPersister) 

- [ ] /dev epic-cook-mode-layout-polish                  
- [ ] /dev epic-cook-mode-multi-recipe-flow   # depends on layout-polish            

- [ ] /dev epic-perf-frontend-fetch-minimization    # closes the fetch tail  first — most user-visible
- [ ] /dev epic-perf-client-analytics # ships the observability backbone (parallel-safe)           
- [ ] /dev epic-perf-debug-tooling # soft-depends on the above two; budgets anchor to post-ffm baseline, ptd-6 hard-depends on cla-1a