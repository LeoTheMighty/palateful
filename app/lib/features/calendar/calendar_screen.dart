import 'package:flutter/material.dart';

/// Placeholder screen for the Calendar tab.
/// Will be replaced with meal planning functionality in Epic 9.
class CalendarScreen extends StatelessWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Calendar')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.calendar_today_outlined, size: 64),
            SizedBox(height: 16),
            Text('Meal planning coming soon'),
          ],
        ),
      ),
    );
  }
}
