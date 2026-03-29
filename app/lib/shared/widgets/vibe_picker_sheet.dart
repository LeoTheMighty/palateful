import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'vibe_chip.dart';

/// Bottom sheet for picking/overriding recipe vibes.
class VibePickerSheet extends StatefulWidget {
  final String? primaryVibe;
  final String? secondaryVibe;
  final void Function(String? primary, String? secondary) onSave;

  const VibePickerSheet({
    super.key,
    this.primaryVibe,
    this.secondaryVibe,
    required this.onSave,
  });

  @override
  State<VibePickerSheet> createState() => _VibePickerSheetState();
}

class _VibePickerSheetState extends State<VibePickerSheet> {
  late String? _primary;
  late String? _secondary;

  @override
  void initState() {
    super.initState();
    _primary = widget.primaryVibe;
    _secondary = widget.secondaryVibe;
  }

  void _onVibeTap(String vibeId) {
    HapticFeedback.selectionClick();
    setState(() {
      if (_primary == vibeId) {
        // Tapping current primary clears it; promote secondary
        _primary = _secondary;
        _secondary = null;
      } else if (_secondary == vibeId) {
        // Tapping current secondary clears it
        _secondary = null;
      } else if (_primary == null) {
        _primary = vibeId;
      } else if (_secondary == null) {
        _secondary = vibeId;
      } else {
        // Both set — replace secondary
        _secondary = vibeId;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final vibes = defaultVibeOptions.values.toList();

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: colorScheme.onSurfaceVariant.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Set Vibes',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(
            'Tap to select primary, tap again for secondary',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: vibes.map((vibe) {
              final isPrimary = _primary == vibe.id;
              final isSecondary = _secondary == vibe.id;
              final isActive = isPrimary || isSecondary;

              return GestureDetector(
                onTap: () => _onVibeTap(vibe.id),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: isActive
                        ? vibe.color.withValues(alpha: 0.25)
                        : colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                    border: isPrimary
                        ? Border.all(color: vibe.color, width: 2)
                        : isSecondary
                            ? Border.all(
                                color: vibe.color.withValues(alpha: 0.5),
                                width: 1)
                            : null,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: isActive
                              ? vibe.color
                              : colorScheme.onSurfaceVariant
                                  .withValues(alpha: 0.3),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        vibe.name,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight:
                              isActive ? FontWeight.w600 : FontWeight.w400,
                          color: isActive
                              ? vibe.color
                              : colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              if (_primary != null || _secondary != null)
                TextButton(
                  onPressed: () {
                    setState(() {
                      _primary = null;
                      _secondary = null;
                    });
                  },
                  child: const Text('Clear all'),
                ),
              const Spacer(),
              FilledButton(
                onPressed: () {
                  widget.onSave(_primary, _secondary);
                  Navigator.of(context).pop();
                },
                child: const Text('Save'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
