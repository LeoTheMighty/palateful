import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:home_widget/home_widget.dart';

const _appGroupId = 'group.com.palateful.app';

/// Service for syncing data from Flutter to iOS home screen widgets.
///
/// Data flows via UserDefaults (App Group) → WidgetKit reads it.
class WidgetDataService {
  bool _initialized = false;

  /// Initialize the widget data bridge. iOS-only — App Groups don't
  /// exist on Android/web, and `home_widget`'s setAppGroupId throws
  /// MissingPluginException off-platform.
  Future<void> initialize() async {
    if (_initialized) return;
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.iOS) return;
    try {
      await HomeWidget.setAppGroupId(_appGroupId);
      _initialized = true;
      debugPrint('WidgetDataService initialized with group: $_appGroupId');
    } catch (e) {
      debugPrint('Failed to initialize WidgetDataService: $e');
    }
  }

  /// Update the next meal widget data.
  Future<void> updateNextMeal({
    required String mealName,
    String? recipeId,
    String? mealTime,
    String? mealType,
  }) async {
    if (!_initialized) return;
    try {
      final data = jsonEncode({
        'name': mealName,
        'recipe_id': recipeId,
        'time': mealTime,
        'type': mealType,
      });
      await HomeWidget.saveWidgetData('next_meal_json', data);
      await HomeWidget.updateWidget(
        iOSName: 'NextMealWidget',
        androidName: 'NextMealWidget',
      );
    } catch (e) {
      debugPrint('Failed to update next meal widget: $e');
    }
  }

  /// Update today's meals for the medium widget.
  Future<void> updateTodayMeals(List<Map<String, dynamic>> meals) async {
    if (!_initialized) return;
    try {
      await HomeWidget.saveWidgetData('today_meals_json', jsonEncode(meals));
      await HomeWidget.updateWidget(
        iOSName: 'NextMealWidget',
        androidName: 'NextMealWidget',
      );
    } catch (e) {
      debugPrint('Failed to update today meals widget: $e');
    }
  }

  /// Update the shopping list widget data.
  Future<void> updateShoppingList({
    required String listId,
    required String listName,
    required int uncheckedCount,
    required List<Map<String, String>> topItems,
  }) async {
    if (!_initialized) return;
    try {
      final data = jsonEncode({
        'list_id': listId,
        'name': listName,
        'unchecked_count': uncheckedCount,
        'items': topItems,
      });
      await HomeWidget.saveWidgetData('shopping_list_json', data);
      await HomeWidget.updateWidget(
        iOSName: 'ShoppingListWidget',
        androidName: 'ShoppingListWidget',
      );
    } catch (e) {
      debugPrint('Failed to update shopping list widget: $e');
    }
  }

  /// Clear all widget data (e.g., on logout).
  Future<void> clear() async {
    if (!_initialized) return;
    try {
      await HomeWidget.saveWidgetData('next_meal_json', null);
      await HomeWidget.saveWidgetData('today_meals_json', null);
      await HomeWidget.saveWidgetData('shopping_list_json', null);
      await HomeWidget.updateWidget(iOSName: 'NextMealWidget', androidName: 'NextMealWidget');
      await HomeWidget.updateWidget(iOSName: 'ShoppingListWidget', androidName: 'ShoppingListWidget');
    } catch (e) {
      debugPrint('Failed to clear widget data: $e');
    }
  }
}
