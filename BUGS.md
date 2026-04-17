Bugs/Improvements:
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
