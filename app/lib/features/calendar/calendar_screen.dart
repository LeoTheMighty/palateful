import 'package:flutter/material.dart';
import '../../shared/widgets/empty_state.dart';

/// Placeholder screen for the Calendar tab.
/// Will be replaced with meal planning functionality in Epic 9.
class CalendarScreen extends StatelessWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Calendar')),
      body: const EmptyStateWidget(
        icon: Icons.calendar_today_outlined,
        title: 'No meals planned yet',
        subtitle: 'Your weekly meal plan will appear here',
      ),
    );
  }
}
