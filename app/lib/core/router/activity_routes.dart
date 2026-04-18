/// Canonical deep-link paths for the Activity Hub.
///
/// Single source of truth so the share-receiving flow (sru-1) stays
/// insulated from the concurrent `epic-activity-hub-redesign` work —
/// if the tab query-param contract ever shifts, update this constant
/// and every caller lands on the right place.
class ActivityRoutes {
  ActivityRoutes._();

  /// The Activity Hub "Imports" tab. After a share completes, the
  /// receiving screen navigates here so the user sees the new job row.
  static const String hubPath = '/activity?tab=imports';
}
