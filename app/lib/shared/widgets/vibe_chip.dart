import 'package:flutter/material.dart';

/// Static vibe metadata. Falls back to these when API is unavailable.
const Map<String, VibeOption> defaultVibeOptions = {
  'light_fresh': VibeOption(id: 'light_fresh', name: 'Light & Fresh', color: Color(0xFFA8D8A8)),
  'hearty': VibeOption(id: 'hearty', name: 'Hearty & Filling', color: Color(0xFFD4A853)),
  'comfort': VibeOption(id: 'comfort', name: 'Comfort', color: Color(0xFFCB8B73)),
  'energizing': VibeOption(id: 'energizing', name: 'Energizing', color: Color(0xFF8FA882)),
  'carb_load': VibeOption(id: 'carb_load', name: 'Carb-Load', color: Color(0xFFC8A96E)),
  'indulgent': VibeOption(id: 'indulgent', name: 'Indulgent', color: Color(0xFF8B6B8B)),
  'warming': VibeOption(id: 'warming', name: 'Warming', color: Color(0xFFA0522D)),
};

class VibeOption {
  final String id;
  final String name;
  final Color color;

  const VibeOption({required this.id, required this.name, required this.color});

  factory VibeOption.fromJson(Map<String, dynamic> json) {
    return VibeOption(
      id: json['id'] as String,
      name: json['name'] as String,
      color: _parseColor(json['color'] as String),
    );
  }

  static Color _parseColor(String hex) {
    final hexStr = hex.replaceFirst('#', '');
    return Color(int.parse('FF$hexStr', radix: 16));
  }
}

/// Colored pill showing a recipe vibe (e.g. "● Comfort" in terracotta).
class VibeChip extends StatelessWidget {
  final String vibeId;
  final bool large;
  final VoidCallback? onTap;

  const VibeChip({
    super.key,
    required this.vibeId,
    this.large = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final option = defaultVibeOptions[vibeId];
    if (option == null) return const SizedBox.shrink();

    final color = option.color;
    final fontSize = large ? 13.0 : 10.0;
    final dotSize = large ? 8.0 : 6.0;
    final hPad = large ? 10.0 : 6.0;
    final vPad = large ? 5.0 : 2.0;

    final chip = Container(
      padding: EdgeInsets.symmetric(horizontal: hPad, vertical: vPad),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(large ? 8 : 4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: dotSize,
            height: dotSize,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          SizedBox(width: large ? 6 : 4),
          Text(
            option.name,
            style: TextStyle(
              fontSize: fontSize,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );

    if (onTap != null) {
      return GestureDetector(onTap: onTap, child: chip);
    }
    return chip;
  }
}

/// Row of vibe chips for a recipe. Shows nothing if no vibes.
class VibeChips extends StatelessWidget {
  final String? primaryVibe;
  final String? secondaryVibe;
  final bool large;
  final VoidCallback? onTap;

  const VibeChips({
    super.key,
    this.primaryVibe,
    this.secondaryVibe,
    this.large = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (primaryVibe == null) return const SizedBox.shrink();

    return Wrap(
      spacing: 6,
      runSpacing: 4,
      children: [
        VibeChip(vibeId: primaryVibe!, large: large, onTap: onTap),
        if (secondaryVibe != null)
          VibeChip(vibeId: secondaryVibe!, large: large, onTap: onTap),
      ],
    );
  }
}
