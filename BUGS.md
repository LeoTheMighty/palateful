Bugs/Improvements:

* Creating a Meal breaks
* PUSH NOTIFICATIONS
* Logging out shows a weird auth0 page
* Change language to be "dismiss" in imports/notifs instead of archive (for successful ones it's weird language)
* Shopping cart still broken
    * Can't open at all because of "Import all from calendar" bug
    * Also still seeing the Websocket errors in crashlytics
* When token needs a refresh sometimes get very strange errors in the app, should detect "need to refresh auth" errors everywhere



=================== old =======

* Still experiencing bug on the current shopping cart after trying to import all ingredients from the calendar.
* **Calendar reminder — 2026-10-08 (day 170 of PI free tier)**: Performance Insights on `palateful-db-prod` switches off free tier around this date. Either keep it (~$2/mo, stays under NFR29's $50 cap) or toggle `performance_insights_enabled=false` in `terraform/modules/rds/main.tf`. Decide before the date so we don't get a surprise bill.
* 

======= OLD =========

* Latency data now lands at `/admin/metrics` (endpoint + task p50/p95/p99 + sparklines). Use this as the first stop before filing a "feels slow" bug.

========== OLD ==============

* Latency metrics on endpoints/tasks would be good. Still don't want to use datadog, wonder what a good way to handle this is
* Feedback from users will be crucial, I want that in the admin section, and also want notifications for it as an admin.
* Also let's make a prod script for fetching feedbacks

======= OLD ============

* Remove the "add image" icon from the top, not useful.
* Really need to get notifications going, I haven't seen a single one work yet. Do we even have firebase setup correctly?
* After you add a recipe, should go back to the current page (like from Photo) going back to the home page is little jarring, esp if we want to add another
* I wonder what would happen if we had two recipes in one image? Would we be smart enough to do it correctly? This feels like something HunyuanOCR could handle, we might be able to have it return separate recipes via a prompt.
* Review Import definitely need to see the unit and quantity and notes here. After extractor changes don't see it at all, probably should be in separate dropdown/unit fields.
* I wonder if the Import has an ability to store the images usually. Would be cool if we were able to grab a crop from the image for this, but I know that could be challenging. For web it might be easier to find and store the URL if that's accessible? But there are probably copyright issues there. Maybe we just have the end of a recipe having an easy to use "Snap Picture".
* We want to be able to change calendars and share calendars with others and have them able to have full edit/add permissions too.

========= OLD ================
* Tapping calendar meal should bring you to the Meal page
    * Maybe some combination of meal and mealplan where you can see the recipe, or reschedule, or unschedule it
    * Hmm honestly it should be a "Day View" when you tap on it, or a specific element based on where you tap. Different levels
    * You should always have a default shopping list, add it to the onboard flow or something
* Calendar needs recurrence, maybe not default but certainly easy to setup.
* When you plan a meal you absolutely need to have a autocomplete with your meals there, a meal should be attached to a meal plan for sure.
* I (leonid@ac93.org or @leo need to be an admin, gotta run a prod script to do that)
* Move the AI assistant out of the main view for now, I want to work on it later but not quite yet.
    * Additionally an MCP makes this virtually useless.
    * Maybe there's somewhere in the app to advertise this, but it's very tech heavy IDK.
* Since with the meal plan, the home screen could become bloated maybe it's best to use a Sort/Filter icon at the top row, move the "Sort" options into that and then get rid of the chat window.
* Maybe we should make our own error tracing in the database... As much as I like to use external resources, crashlytics won't be useful if you or I can't really read it.
    * Could build it out so that I as an admin can look at everyone's errors too... can't do that with crashlytics huh
    * Maybe I should use both ?
* Activity Hub
    * Needs a proper re-do and we need consolidate both the import activity in the "Add Recipe" page, I want that experience in the Activity hub/import hub
    * These notifications still aren't "readable" they don't go away and I can't get them to leave
    * Also there's literally information in the import activity that I can't see


======== OLD ===========


* Activity tab - Needs Review shows up but when I tap it nothing shows up, seems broken.
* Activity tab has "Photo OCR failed" but every time I go to it it's unread, can read in the moment, but going back always shows unread
* Activity tab always has a big number of unread. Is 'reading' working? 
* Import activity shows a (1) but then has "All Set", similar to needs review maybe?
* Calendar completely broken tried to add a meal but now it says failed to load calendar every time I go there
* Maybe recipe book icon to the left of the search bar?
* I like the in progress tab in the Add Recipe, but it should be how the Import Activity looks like. Currently the import history looks bad. "0 / 1 imported" confusing
