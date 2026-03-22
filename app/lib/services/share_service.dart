import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import '../core/di/injection.dart';
import '../core/services/api_client.dart';

/// Unified sharing service for recipes, recipe books, and shopping lists.
///
/// Handles link generation via API and opens the native iOS share sheet
/// with iPad-safe `sharePositionOrigin`.
class ShareService {
  final ApiClient _apiClient;

  ShareService({ApiClient? apiClient})
      : _apiClient = apiClient ?? getIt<ApiClient>();

  /// Calculate share position origin for iPad safety.
  static Rect? originFrom(BuildContext context) {
    final box = context.findRenderObject() as RenderBox?;
    if (box == null) return null;
    return box.localToGlobal(Offset.zero) & box.size;
  }

  /// Share a recipe via native share sheet.
  /// Generates a public share link, then opens the share sheet.
  Future<void> shareRecipe({
    required String recipeId,
    required String recipeName,
    required BuildContext context,
  }) async {
    final response = await _apiClient.shareRecipe(recipeId);
    final deepLink = response.data['deep_link'] as String?;
    final token = response.data['share_token'] as String?;

    final link = deepLink ?? 'https://palateful.app/recipes/shared/$token';
    final text = 'Check out "$recipeName" on Palateful!\n$link';

    await Share.share(
      text,
      subject: recipeName,
      sharePositionOrigin: originFrom(context),
    );
  }

  /// Share a recipe book via invite link + native share sheet.
  Future<void> shareRecipeBook({
    required String recipeBookId,
    required String recipeBookName,
    required BuildContext context,
  }) async {
    final response = await _apiClient.createInviteLink({
      'resource_type': 'recipe_book',
      'resource_id': recipeBookId,
      'role_offered': 'viewer',
    });

    final data = response.data as Map<String, dynamic>;
    final link = data['link'] as String? ?? data['deep_link'] as String? ?? '';
    final text = 'Join my recipe book "$recipeBookName" on Palateful!\n$link';

    await Share.share(
      text,
      subject: 'Join $recipeBookName',
      sharePositionOrigin: originFrom(context),
    );
  }

  /// Share a shopping list via deep link + native share sheet.
  Future<void> shareShoppingList({
    required String listId,
    required String listName,
    required BuildContext context,
  }) async {
    final response = await _apiClient.shareShoppingList(listId);
    final data = response.data as Map<String, dynamic>;
    final shareCode = data['share_code'] as String;
    final deepLink = data['deep_link'] as String?;

    final link = deepLink ?? 'palateful://shopping-list/join/$shareCode';
    final text = 'Join my shopping list "$listName" on Palateful!\n$link';

    await Share.share(
      text,
      subject: 'Join $listName',
      sharePositionOrigin: originFrom(context),
    );
  }
}
