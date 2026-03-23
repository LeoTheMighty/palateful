import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:home_widget/home_widget.dart';

const _appGroupId = 'group.com.palateful.app';

/// Service for indexing recipes in iOS Spotlight Search and
/// providing recipe data for Siri App Intents.
class SpotlightIndexService {
  static const _channel = MethodChannel('com.palateful.spotlight');

  /// Index a list of recipes for Siri entity resolution.
  ///
  /// Writes a lightweight recipe name→ID mapping to shared UserDefaults
  /// so native App Intents can resolve recipe names to IDs.
  Future<void> updateRecipeIndex(List<Map<String, dynamic>> recipes) async {
    if (!Platform.isIOS) return;
    try {
      final index = recipes.map((r) => {
        'id': r['id']?.toString() ?? '',
        'name': r['name']?.toString() ?? '',
        'book_name': r['book_name']?.toString() ?? '',
      }).toList();
      await HomeWidget.saveWidgetData('recipes_index_json', jsonEncode(index));
    } catch (e) {
      debugPrint('Failed to update recipe index: $e');
    }
  }

  /// Index a single recipe in Spotlight search.
  Future<void> indexRecipe({
    required String id,
    required String name,
    String? description,
    String? imageUrl,
    List<String>? tags,
  }) async {
    if (!Platform.isIOS) return;
    try {
      await _channel.invokeMethod('indexRecipe', {
        'id': id,
        'name': name,
        'description': description,
        'imageUrl': imageUrl,
        'tags': tags,
      });
    } catch (e) {
      debugPrint('Failed to index recipe in Spotlight: $e');
    }
  }

  /// Remove a recipe from Spotlight search.
  Future<void> deindexRecipe(String id) async {
    if (!Platform.isIOS) return;
    try {
      await _channel.invokeMethod('deindexRecipe', {'id': id});
    } catch (e) {
      debugPrint('Failed to deindex recipe: $e');
    }
  }
}
