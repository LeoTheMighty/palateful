import 'package:flutter/material.dart';

/// Placeholder screen for the Cart tab.
/// Will be replaced with full shopping list functionality in Epic 8.
class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cart')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.shopping_cart_outlined, size: 64),
            SizedBox(height: 16),
            Text('Shopping list coming soon'),
          ],
        ),
      ),
    );
  }
}
