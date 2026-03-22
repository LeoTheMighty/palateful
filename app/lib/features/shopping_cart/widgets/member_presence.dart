import 'package:flutter/material.dart';

import '../../../core/theme/theme.dart';
import '../models/shopping_list.dart';

/// Widget showing online members of a shared shopping list.
class MemberPresence extends StatelessWidget {
  final List<OnlineUser> onlineUsers;
  final int maxVisible;
  final double avatarSize;

  const MemberPresence({
    super.key,
    required this.onlineUsers,
    this.maxVisible = 3,
    this.avatarSize = 28,
  });

  @override
  Widget build(BuildContext context) {
    if (onlineUsers.isEmpty) {
      return const SizedBox.shrink();
    }

    final visibleUsers = onlineUsers.take(maxVisible).toList();
    final extraCount = onlineUsers.length - maxVisible;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Stacked avatars
        SizedBox(
          width: _calculateWidth(visibleUsers.length, extraCount > 0),
          height: avatarSize,
          child: Stack(
            children: [
              for (int i = 0; i < visibleUsers.length; i++)
                Positioned(
                  left: i * (avatarSize * 0.7),
                  child: _MemberAvatar(
                    user: visibleUsers[i],
                    size: avatarSize,
                  ),
                ),
              if (extraCount > 0)
                Positioned(
                  left: visibleUsers.length * (avatarSize * 0.7),
                  child: _ExtraCountBadge(
                    count: extraCount,
                    size: avatarSize,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  double _calculateWidth(int visibleCount, bool hasExtra) {
    final count = visibleCount + (hasExtra ? 1 : 0);
    if (count == 0) return 0;
    return avatarSize + (count - 1) * (avatarSize * 0.7);
  }
}

class _MemberAvatar extends StatelessWidget {
  final OnlineUser user;
  final double size;

  const _MemberAvatar({
    required this.user,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final appColors = context.appColors;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _getAvatarColor(colorScheme, appColors),
        border: Border.all(color: colorScheme.surface, width: 2),
        borderRadius: BorderRadius.circular(size / 2),
        boxShadow: [
          BoxShadow(
            color: colorScheme.shadow,
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Stack(
        children: [
          Center(
            child: Text(
              _getInitials(),
              style: TextStyle(
                fontSize: size * 0.4,
                fontWeight: FontWeight.w600,
                color: colorScheme.surface,
              ),
            ),
          ),
          // Online status indicator
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              width: size * 0.35,
              height: size * 0.35,
              decoration: BoxDecoration(
                color: user.isShopping ? appColors.success : appColors.info,
                border: Border.all(color: colorScheme.surface, width: 2),
                borderRadius: BorderRadius.circular(size * 0.175),
              ),
              child: user.isShopping
                  ? Icon(
                      Icons.shopping_cart,
                      size: size * 0.2,
                      color: colorScheme.surface,
                    )
                  : null,
            ),
          ),
        ],
      ),
    );
  }

  Color _getAvatarColor(ColorScheme colorScheme, PalatefulColors appColors) {
    if (user.name == null || user.name!.isEmpty) {
      return colorScheme.secondary;
    }
    // Generate consistent color from name
    final hash = user.name.hashCode;
    final colors = [
      colorScheme.primary,
      colorScheme.secondary,
      colorScheme.tertiary,
      appColors.success,
      appColors.info,
    ];
    return colors[hash.abs() % colors.length];
  }

  String _getInitials() {
    if (user.name == null || user.name!.isEmpty) {
      return '?';
    }
    final parts = user.name!.split(' ');
    if (parts.length >= 2) {
      return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    }
    return user.name![0].toUpperCase();
  }
}

class _ExtraCountBadge extends StatelessWidget {
  final int count;
  final double size;

  const _ExtraCountBadge({
    required this.count,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest,
        border: Border.all(color: colorScheme.surface, width: 2),
        borderRadius: BorderRadius.circular(size / 2),
      ),
      child: Center(
        child: Text(
          '+$count',
          style: TextStyle(
            fontSize: size * 0.35,
            fontWeight: FontWeight.w600,
            color: colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

/// Compact presence indicator with just a colored dot.
class PresenceIndicator extends StatelessWidget {
  final bool isOnline;
  final bool isShopping;
  final double size;

  const PresenceIndicator({
    super.key,
    required this.isOnline,
    this.isShopping = false,
    this.size = 8,
  });

  @override
  Widget build(BuildContext context) {
    final appColors = context.appColors;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: isOnline
            ? (isShopping ? appColors.success : appColors.info)
            : appColors.textDisabled,
        borderRadius: BorderRadius.circular(size / 2),
      ),
    );
  }
}
