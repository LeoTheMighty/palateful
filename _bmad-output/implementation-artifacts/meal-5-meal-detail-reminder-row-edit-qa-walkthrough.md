# QA walkthrough — meal-5

Story: `meal-5-meal-detail-reminder-row-edit` (epic
`notifications-meal-reminders`).

## Visual

- [ ] Open a meal from the calendar week view → meal detail screen.
- [ ] Below the meal-type / "Shared" chip row, a **Reminder** section
      is visible.
- [ ] A meal with no override shows e.g. `12:00 PM (Lunch default)`
      with a bell icon and a small edit icon on the right.
- [ ] A meal whose `meal_reminder_time` is set shows the explicit time
      without the "default" caption — a **Reset to default** link is
      visible to the right of the "Reminder" label.

## Happy path — override

- [ ] Tap the reminder row → Material time picker opens at the
      current resolved value.
- [ ] Change to e.g. 11:45 AM, confirm.
- [ ] Row flashes a small spinner (no Save button needed) and
      re-renders with **11:45 AM** and no caption; Reset link appears.

## Happy path — reset

- [ ] With an override set, tap **Reset to default**.
- [ ] Row re-renders back to the slot default (e.g. lunch → 12:00 PM)
      with the caption "(Lunch default)" and the Reset link gone.

## Shared-meal side effects (meal-4)

- [ ] Sarah edits the reminder on a shared meal Leo is accepted to →
      Leo receives a `MEAL_EVENT_UPDATED` push ("Brunch updated" /
      "Sarah made changes to 'Brunch'"), tap lands on the detail
      screen.
- [ ] Sarah doesn't receive one for her own edit.

## Error path

- [ ] Turn Wi-Fi off, tap the reminder row, pick a new time, confirm.
- [ ] A snackbar reads "Failed to update reminder time." The row
      reverts to the prior value. `ErrorReporter.report` is called
      with `area: calendar`, `operation: meal_detail.set_reminder_time`.

## Not in scope

- Picker long-press for Reset (kept as an explicit inline text button
  for discoverability; epic spec AC 3 left this at implementer's
  discretion).
