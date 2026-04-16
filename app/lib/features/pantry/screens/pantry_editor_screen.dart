import 'package:flutter/material.dart';

/// Stub editor — replaced by the full form in pantry-6.
class PantryEditorScreen extends StatelessWidget {
  final String ingredientId;

  const PantryEditorScreen({super.key, required this.ingredientId});

  @override
  Widget build(BuildContext context) {
    final isNew = ingredientId == 'new';
    return Scaffold(
      appBar: AppBar(
        title: Text(isNew ? 'Add pantry item' : 'Edit pantry item'),
      ),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'The full pantry editor lands in pantry-6. '
            'For now use the shopping-list flow or the AI assistant to add items.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
