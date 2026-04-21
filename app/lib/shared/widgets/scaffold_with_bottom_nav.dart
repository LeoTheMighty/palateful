import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/utils/responsive.dart';
import '../../features/activity/providers/activity_read_provider.dart';

/// Shell widget that provides adaptive navigation for the main app tabs.
/// Uses bottom NavigationBar on mobile (<600px) and NavigationRail on wider screens.
class ScaffoldWithBottomNav extends StatefulWidget {
  final StatefulNavigationShell navigationShell;

  const ScaffoldWithBottomNav({
    super.key,
    required this.navigationShell,
  });

  @override
  State<ScaffoldWithBottomNav> createState() => _ScaffoldWithBottomNavState();
}

class _ScaffoldWithBottomNavState extends State<ScaffoldWithBottomNav> {
  final _readProvider = getIt<ActivityReadProvider>();

  @override
  void initState() {
    super.initState();
    _readProvider.unreadCount.addListener(_onCountChanged);
    // pfc-1: single source of cadence. startPolling fires an immediate
    // tick for cold-start reconciliation, then installs the 30s Timer.
    _readProvider.startPolling();
  }

  @override
  void dispose() {
    _readProvider.unreadCount.removeListener(_onCountChanged);
    _readProvider.stopPolling();
    super.dispose();
  }

  void _onCountChanged() {
    if (mounted) setState(() {});
  }

  void _onDestinationSelected(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
    // Refresh badge when switching to Activity tab
    if (index == 2) _readProvider.refreshUnreadCount();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.of(context).disableAnimations;
    final isWide = !ResponsiveUtils.isMobile(context);
    final unreadCount = _readProvider.unreadCount.value;
    final showBadge = unreadCount > 0;
    final badgeLabel = unreadCount > 99 ? '99+' : '$unreadCount';
    // abi-3: Semantic label spells out the exact count so screen readers
    // aren't truncated when the visual pill shows "99+". Only emitted
    // when the badge is visible.
    final semanticLabel = showBadge ? '$unreadCount unread items' : null;

    if (isWide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: widget.navigationShell.currentIndex,
              onDestinationSelected: _onDestinationSelected,
              labelType: NavigationRailLabelType.all,
              destinations: [
                const NavigationRailDestination(
                  icon: Icon(Icons.home_outlined),
                  selectedIcon: Icon(Icons.home),
                  label: Text('Home'),
                ),
                const NavigationRailDestination(
                  icon: Icon(Icons.shopping_cart_outlined),
                  selectedIcon: Icon(Icons.shopping_cart),
                  label: Text('Cart'),
                ),
                NavigationRailDestination(
                  icon: Semantics(
                    label: semanticLabel,
                    child: Badge(
                      label: Text(badgeLabel),
                      isLabelVisible: showBadge,
                      child: const Icon(Icons.notifications_outlined),
                    ),
                  ),
                  selectedIcon: Semantics(
                    label: semanticLabel,
                    child: Badge(
                      label: Text(badgeLabel),
                      isLabelVisible: showBadge,
                      child: const Icon(Icons.notifications),
                    ),
                  ),
                  label: const Text('Activity'),
                ),
                const NavigationRailDestination(
                  icon: Icon(Icons.calendar_today_outlined),
                  selectedIcon: Icon(Icons.calendar_today),
                  label: Text('Calendar'),
                ),
                const NavigationRailDestination(
                  icon: Icon(Icons.person_outline),
                  selectedIcon: Icon(Icons.person),
                  label: Text('Profile'),
                ),
              ],
            ),
            const VerticalDivider(thickness: 1, width: 1),
            Expanded(child: widget.navigationShell),
          ],
        ),
      );
    }

    // Mobile: bottom navigation bar
    return Scaffold(
      body: widget.navigationShell,
      bottomNavigationBar: NavigationBar(
        animationDuration: reduceMotion ? Duration.zero : const Duration(milliseconds: 400),
        selectedIndex: widget.navigationShell.currentIndex,
        onDestinationSelected: _onDestinationSelected,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          const NavigationDestination(
            icon: Icon(Icons.shopping_cart_outlined),
            selectedIcon: Icon(Icons.shopping_cart),
            label: 'Cart',
          ),
          NavigationDestination(
            icon: Semantics(
              label: semanticLabel,
              child: Badge(
                label: Text(badgeLabel),
                isLabelVisible: showBadge,
                child: const Icon(Icons.notifications_outlined),
              ),
            ),
            selectedIcon: Semantics(
              label: semanticLabel,
              child: Badge(
                label: Text(badgeLabel),
                isLabelVisible: showBadge,
                child: const Icon(Icons.notifications),
              ),
            ),
            label: 'Activity',
          ),
          const NavigationDestination(
            icon: Icon(Icons.calendar_today_outlined),
            selectedIcon: Icon(Icons.calendar_today),
            label: 'Calendar',
          ),
          const NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}
