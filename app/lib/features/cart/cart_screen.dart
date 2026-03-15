import 'package:flutter/material.dart';
import '../../shared/widgets/empty_state.dart';

/// Placeholder screen for the Cart tab.
/// Will be replaced with full shopping list functionality in Epic 8.
class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cart')),
      body: const EmptyStateWidget(
        icon: Icons.shopping_cart_outlined,
        title: 'No shopping lists yet',
        subtitle: 'Plan a meal and add ingredients to get started',
      ),
    );
  }
}
