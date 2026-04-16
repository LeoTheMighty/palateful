import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';

/// Categorization of how urgent an expiry is — drives color + copy.
enum ExpiryUrgency {
  expired, // already past expiry
  today, // 0 days
  tomorrow, // 1 day
  soon, // 2–3 days
  fresh, // 4–7 days
  plenty, // 7+ days
  none, // no date set
}

class FuzzyExpiry {
  final String label;
  final ExpiryUrgency urgency;

  const FuzzyExpiry({required this.label, required this.urgency});

  Color get barColor {
    switch (urgency) {
      case ExpiryUrgency.expired:
      case ExpiryUrgency.today:
      case ExpiryUrgency.tomorrow:
      case ExpiryUrgency.soon:
        return AppColors.error;
      case ExpiryUrgency.fresh:
        return AppColors.warning;
      case ExpiryUrgency.plenty:
        return AppColors.success;
      case ExpiryUrgency.none:
        return AppColors.textSecondary;
    }
  }
}

/// Deterministic text + urgency bucket for an expiry date.
///
/// Rules (from the epic Dev Notes):
///   < 0 days  → "Expired"
///   0 days    → "Expires today"
///   1 day     → "Expires tomorrow"
///   2–3 days  → "Expires in N days"
///   4–7 days  → "Good for ~N days" (amber)
///   > 7 days  → "Good for ~N days" (green)
///   null      → "No expiry set"
FuzzyExpiry fuzzyExpiry(DateTime? expiresAt, {DateTime? now}) {
  if (expiresAt == null) {
    return const FuzzyExpiry(
      label: 'No expiry set',
      urgency: ExpiryUrgency.none,
    );
  }
  final reference = now ?? DateTime.now();
  // Compare at day granularity so "expires in 6 hours" still reads as today.
  final todayStart = DateTime(reference.year, reference.month, reference.day);
  final expiryStart =
      DateTime(expiresAt.year, expiresAt.month, expiresAt.day);
  final days = expiryStart.difference(todayStart).inDays;

  if (days < 0) {
    return const FuzzyExpiry(label: 'Expired', urgency: ExpiryUrgency.expired);
  }
  if (days == 0) {
    return const FuzzyExpiry(
      label: 'Expires today',
      urgency: ExpiryUrgency.today,
    );
  }
  if (days == 1) {
    return const FuzzyExpiry(
      label: 'Expires tomorrow',
      urgency: ExpiryUrgency.tomorrow,
    );
  }
  if (days <= 3) {
    return FuzzyExpiry(
      label: 'Expires in $days days',
      urgency: ExpiryUrgency.soon,
    );
  }
  if (days <= 7) {
    return FuzzyExpiry(
      label: 'Good for ~$days days',
      urgency: ExpiryUrgency.fresh,
    );
  }
  return FuzzyExpiry(
    label: 'Good for ~$days days',
    urgency: ExpiryUrgency.plenty,
  );
}
