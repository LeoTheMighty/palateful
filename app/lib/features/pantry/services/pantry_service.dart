import 'dart:async';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../models/pantry.dart';
import '../models/pantry_ingredient.dart';

/// StreamController-based service for the user's default pantry.
///
/// Mirrors the pattern established by [ShoppingCartService] — plain streams,
/// no Bloc/Riverpod.
class PantryService {
  final ApiClient _apiClient = getIt<ApiClient>();

  final _pantryController = StreamController<Pantry?>.broadcast();
  Pantry? _current;

  Stream<Pantry?> get pantryStream => _pantryController.stream;
  Pantry? get current => _current;

  Future<void> loadDefaultPantry() async {
    final response = await _apiClient.getDefaultPantry();
    final pantry = Pantry.fromJson(response.data as Map<String, dynamic>);
    _current = pantry;
    _pantryController.add(pantry);
  }

  Future<PantryIngredient> addPantryIngredient(
    String pantryId,
    Map<String, dynamic> data,
  ) async {
    final response = await _apiClient.addPantryIngredient(pantryId, data);
    final added = PantryIngredient.fromJson(response.data as Map<String, dynamic>);
    final current = _current;
    if (current != null && current.id == pantryId) {
      final next = List<PantryIngredient>.from(current.items)
        ..removeWhere((i) => i.ingredientId == added.ingredientId)
        ..add(added);
      _current = current.copyWith(items: next);
      _pantryController.add(_current);
    }
    return added;
  }

  /// Optimistically removes the row from the cached pantry and issues the
  /// DELETE. On failure the caller is responsible for rollback — we don't
  /// own the snackbar here.
  Future<void> deletePantryIngredient(
    String pantryId,
    String ingredientId,
  ) async {
    final current = _current;
    if (current != null && current.id == pantryId) {
      final next = current.items
          .where((i) => i.ingredientId != ingredientId)
          .toList();
      _current = current.copyWith(items: next);
      _pantryController.add(_current);
    }
    try {
      await _apiClient.deletePantryIngredient(pantryId, ingredientId);
    } catch (_) {
      // Reload to resync on failure.
      await loadDefaultPantry();
      rethrow;
    }
  }

  void dispose() {
    _pantryController.close();
  }
}
