import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/theme.dart';

/// Primary action button with rich chocolate background.
/// Use for main CTAs like "Save", "Continue", "Submit".
class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isExpanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isLoading;
  final bool isExpanded;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final button = ElevatedButton(
      onPressed: isLoading ? null : onPressed,
      child: isLoading
          ? SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: colorScheme.surface,
              ),
            )
          : icon != null
              ? Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, size: 20),
                    const SizedBox(width: 8),
                    Text(label),
                  ],
                )
              : Text(label),
    );

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

/// Secondary outlined button with hazelnut border.
/// Use for secondary actions like "Cancel", "Back", "Skip".
class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isExpanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isLoading;
  final bool isExpanded;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final button = OutlinedButton(
      onPressed: isLoading ? null : onPressed,
      child: isLoading
          ? SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: colorScheme.secondary,
              ),
            )
          : icon != null
              ? Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, size: 20),
                    const SizedBox(width: 8),
                    Text(label),
                  ],
                )
              : Text(label),
    );

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

/// Text-only button for tertiary actions.
/// Use for low-emphasis actions like "Learn more", links.
class TertiaryButton extends StatelessWidget {
  const TertiaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isExpanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isExpanded;

  @override
  Widget build(BuildContext context) {
    final button = TextButton(
      onPressed: onPressed,
      child: icon != null
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 18),
                const SizedBox(width: 6),
                Text(label),
              ],
            )
          : Text(label),
    );

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

/// Soft button with subtle background, no border.
/// Great for inline actions within cards or lists.
class SoftButton extends StatelessWidget {
  const SoftButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.color,
    this.isExpanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Color? color;
  final bool isExpanded;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final baseColor = color ?? colorScheme.primary;

    final button = TextButton(
      onPressed: onPressed,
      style: TextButton.styleFrom(
        backgroundColor: baseColor.withValues(alpha: 0.08),
        foregroundColor: baseColor,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
      child: icon != null
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 18),
                const SizedBox(width: 6),
                Text(label),
              ],
            )
          : Text(label),
    );

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

/// Icon-only button with circular shape.
/// Use for compact actions in toolbars, cards.
class CircleIconButton extends StatelessWidget {
  const CircleIconButton({
    super.key,
    required this.icon,
    required this.onPressed,
    this.size = 44,
    this.color,
    this.backgroundColor,
    this.tooltip,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final double size;
  final Color? color;
  final Color? backgroundColor;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    final iconColor = color ?? colorScheme.onSurface;
    final bgColor = backgroundColor ?? Colors.transparent;

    final button = Material(
      color: bgColor,
      shape: const CircleBorder(),
      child: InkWell(
        onTap: () {
          HapticFeedback.lightImpact();
          onPressed?.call();
        },
        customBorder: const CircleBorder(),
        splashColor: iconColor.withValues(alpha: 0.15),
        highlightColor: iconColor.withValues(alpha: 0.08),
        mouseCursor: onPressed != null
            ? SystemMouseCursors.click
            : SystemMouseCursors.basic,
        child: SizedBox(
          width: size,
          height: size,
          child: Icon(
            icon,
            color: onPressed != null ? iconColor : appColors.textDisabled,
            size: size * 0.5,
          ),
        ),
      ),
    );

    if (tooltip != null) {
      return Tooltip(message: tooltip!, child: button);
    }
    return button;
  }
}

/// Pill-shaped action button, great for tags and filters.
class PillButton extends StatelessWidget {
  const PillButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isSelected = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isSelected;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: isSelected ? colorScheme.primary : colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: () {
          HapticFeedback.selectionClick();
          onPressed?.call();
        },
        borderRadius: BorderRadius.circular(20),
        mouseCursor: onPressed != null
            ? SystemMouseCursors.click
            : SystemMouseCursors.basic,
        splashColor: isSelected
            ? colorScheme.surface.withValues(alpha: 0.2)
            : colorScheme.primary.withValues(alpha: 0.1),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(
                  icon,
                  size: 16,
                  color: isSelected ? colorScheme.surface : colorScheme.onSurface,
                ),
                const SizedBox(width: 6),
              ],
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? colorScheme.surface : colorScheme.onSurface,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Danger/destructive action button.
/// Use for delete, remove, or other destructive actions.
class DangerButton extends StatelessWidget {
  const DangerButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isExpanded = false,
    this.outlined = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isExpanded;
  final bool outlined;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final Widget button;

    if (outlined) {
      button = OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          foregroundColor: colorScheme.error,
          side: BorderSide(color: colorScheme.error, width: 1.5),
        ),
        child: _buildChild(),
      );
    } else {
      button = ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: colorScheme.error,
          foregroundColor: colorScheme.surface,
        ),
        child: _buildChild(),
      );
    }

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }

  Widget _buildChild() {
    if (icon != null) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: 8),
          Text(label),
        ],
      );
    }
    return Text(label);
  }
}

/// Success action button with sage green color.
class SuccessButton extends StatelessWidget {
  const SuccessButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isExpanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isExpanded;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    final button = ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: appColors.success,
        foregroundColor: colorScheme.surface,
      ),
      child: icon != null
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 20),
                const SizedBox(width: 8),
                Text(label),
              ],
            )
          : Text(label),
    );

    return isExpanded
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

/// Animated scale button wrapper for extra tactile feedback.
/// Wraps any widget and adds a press animation.
class ScaleTapButton extends StatefulWidget {
  const ScaleTapButton({
    super.key,
    required this.child,
    required this.onPressed,
    this.scaleDown = 0.96,
    this.haptic = true,
  });

  final Widget child;
  final VoidCallback? onPressed;
  final double scaleDown;
  final bool haptic;

  @override
  State<ScaleTapButton> createState() => _ScaleTapButtonState();
}

class _ScaleTapButtonState extends State<ScaleTapButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    );
    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: widget.scaleDown,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onTapDown(TapDownDetails details) {
    _controller.forward();
  }

  void _onTapUp(TapUpDetails details) {
    _controller.reverse();
    if (widget.haptic) {
      HapticFeedback.lightImpact();
    }
    widget.onPressed?.call();
  }

  void _onTapCancel() {
    _controller.reverse();
  }

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: widget.onPressed != null
          ? SystemMouseCursors.click
          : SystemMouseCursors.basic,
      child: GestureDetector(
        onTapDown: widget.onPressed != null ? _onTapDown : null,
        onTapUp: widget.onPressed != null ? _onTapUp : null,
        onTapCancel: widget.onPressed != null ? _onTapCancel : null,
        child: ScaleTransition(
          scale: _scaleAnimation,
          child: widget.child,
        ),
      ),
    );
  }
}
