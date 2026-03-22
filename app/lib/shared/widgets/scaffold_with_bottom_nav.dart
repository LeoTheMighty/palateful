import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/utils/responsive.dart';

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
  int _unreadCount = 0;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _fetchUnreadCount();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _fetchUnreadCount();
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _fetchUnreadCount() async {
    try {
      final response = await getIt<ApiClient>().getUnreadActivityCount();
      if (!mounted) return;
      final count = response.data['count'] as int? ?? 0;
      if (count != _unreadCount) {
        setState(() => _unreadCount = count);
      }
    } catch (_) {}
  }

  void _onDestinationSelected(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
    // Refresh badge when switching to Activity tab
    if (index == 2) _fetchUnreadCount();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.of(context).disableAnimations;
    final isWide = !ResponsiveUtils.isMobile(context);
    final showBadge = _unreadCount > 0;
    final badgeLabel = _unreadCount > 99 ? '99+' : '$_unreadCount';

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
                  icon: Badge(
                    label: Text(badgeLabel),
                    isLabelVisible: showBadge,
                    child: const Icon(Icons.notifications_outlined),
                  ),
                  selectedIcon: Badge(
                    label: Text(badgeLabel),
                    isLabelVisible: showBadge,
                    child: const Icon(Icons.notifications),
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
            icon: Badge(
              label: Text(badgeLabel),
              isLabelVisible: showBadge,
              child: const Icon(Icons.notifications_outlined),
            ),
            selectedIcon: Badge(
              label: Text(badgeLabel),
              isLabelVisible: showBadge,
              child: const Icon(Icons.notifications),
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
