import 'package:flutter/foundation.dart';
import 'package:home_widget/home_widget.dart';

const _appGroupId = 'group.com.palateful.app';

/// Service for syncing data from Flutter to iOS home screen widgets.
///
/// Data flows via UserDefaults (App Group) → WidgetKit reads it.
class WidgetDataService {
  bool _initialized = false;

  /// Initialize the widget data bridge.
  Future<void> initialize() async {
    if (_initialized) return;
    try {
      await HomeWidget.setAppGroupId(_appGroupId);
      _initialized = true;
      debugPrint('WidgetDataService initialized with group: $_appGroupId');
    } catch (e) {
      debugPrint('Failed to initialize WidgetDataService: $e');
    }
  }

  /// Update the next meal name displayed in the widget.
  Future<void> updateNextMeal({
    required String mealName,
    String? recipeId,
  }) async {
    if (!_initialized) return;
    try {
      await HomeWidget.saveWidgetData('next_meal_name', mealName);
      if (recipeId != null) {
        await HomeWidget.saveWidgetData('next_meal_recipe_id', recipeId);
      }
      await HomeWidget.updateWidget(
        iOSName: 'NextMealWidget',
        androidName: 'NextMealWidget',
      );
    } catch (e) {
      debugPrint('Failed to update widget data: $e');
    }
  }

  /// Clear widget data (e.g., on logout).
  Future<void> clear() async {
    if (!_initialized) return;
    try {
      await HomeWidget.saveWidgetData('next_meal_name', null);
      await HomeWidget.saveWidgetData('next_meal_recipe_id', null);
      await HomeWidget.updateWidget(
        iOSName: 'NextMealWidget',
        androidName: 'NextMealWidget',
      );
    } catch (e) {
      debugPrint('Failed to clear widget data: $e');
    }
  }
}
