import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/di/injection.dart';
import '../../../core/theme/app_colors.dart';
import '../models/shopping_list.dart';
import '../models/shopping_list_item.dart';
import '../services/shopping_cart_service.dart';
import 'member_presence.dart';
import 'shopping_list_item_tile.dart';

/// Floating shopping cart widget that persists across screens.
class FloatingCartWidget extends StatefulWidget {
  final String? listId;
  final Widget child;

  const FloatingCartWidget({
    super.key,
    this.listId,
    required this.child,
  });

  @override
  State<FloatingCartWidget> createState() => _FloatingCartWidgetState();
}

class _FloatingCartWidgetState extends State<FloatingCartWidget>
    with SingleTickerProviderStateMixin {
  late final ShoppingCartService _service;
  late final AnimationController _expandController;
  late final Animation<double> _expandAnimation;

  ShoppingList? _list;
  List<OnlineUser> _onlineUsers = [];
  bool _isExpanded = false;
  bool _isLoading = true;
  String? _error;
  WebSocketState _connectionState = WebSocketState.disconnected;

  // Stream subscriptions
  StreamSubscription? _itemAddedSub;
  StreamSubscription? _itemUpdatedSub;
  StreamSubscription? _itemRemovedSub;
  StreamSubscription? _presenceSub;
  StreamSubscription? _syncSub;
  StreamSubscription? _connectionSub;

  @override
  void initState() {
    super.initState();
    _service = getIt<ShoppingCartService>();

    _expandController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _expandAnimation = CurvedAnimation(
      parent: _expandController,
      curve: Curves.easeOutCubic,
    );

    _setupSubscriptions();

    if (widget.listId != null) {
      _loadList(widget.listId!);
    }
  }

  @override
  void didUpdateWidget(FloatingCartWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.listId != oldWidget.listId && widget.listId != null) {
      _loadList(widget.listId!);
    }
  }

  void _setupSubscriptions() {
    _itemAddedSub = _service.onItemAdded.listen(_handleItemAdded);
    _itemUpdatedSub = _service.onItemUpdated.listen(_handleItemUpdated);
    _itemRemovedSub = _service.onItemRemoved.listen(_handleItemRemoved);
    _presenceSub = _service.onPresenceUpdate.listen(_handlePresenceUpdate);
    _syncSub = _service.onSync.listen(_handleSync);
    _connectionSub =
        _service.onWebSocketStateChange.listen(_handleWebSocketState);
  }

  Future<void> _loadList(String listId) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final list = await _service.getShoppingList(listId);
      if (mounted) {
        setState(() {
          _list = list;
          _isLoading = false;
        });
        _service.connectWebSocket(listId);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load shopping list';
          _isLoading = false;
        });
      }
    }
  }

  void _handleItemAdded(ShoppingListItem item) {
    if (_list == null) return;
    setState(() {
      _list = _list!.copyWith(
        items: [..._list!.items, item],
      );
    });
  }

  void _handleItemUpdated(ShoppingListItem item) {
    if (_list == null) return;
    setState(() {
      final items = _list!.items.map((i) => i.id == item.id ? item : i).toList();
      _list = _list!.copyWith(items: items);
    });
  }

  void _handleItemRemoved(String itemId) {
    if (_list == null) return;
    setState(() {
      final items = _list!.items.where((i) => i.id != itemId).toList();
      _list = _list!.copyWith(items: items);
    });
  }

  void _handlePresenceUpdate(OnlineUser user) {
    setState(() {
      _onlineUsers = [
        ..._onlineUsers.where((u) => u.id != user.id),
        if (user.isOnline) user,
      ];
    });
  }

  void _handleSync(SyncResponse sync) {
    // Handle sync events - could replay them to update state
    setState(() {
      _onlineUsers = sync.onlineUsers
          .map((id) => OnlineUser(id: id, timestamp: DateTime.now()))
          .toList();
    });
  }

  void _handleWebSocketState(WebSocketState state) {
    setState(() {
      _connectionState = state;
    });
  }

  void _toggleExpanded() {
    HapticFeedback.mediumImpact();
    setState(() {
      _isExpanded = !_isExpanded;
    });
    if (_isExpanded) {
      _expandController.forward();
      _service.updatePresence('shopping');
    } else {
      _expandController.reverse();
      _service.updatePresence('online');
    }
  }

  Future<void> _toggleItemChecked(ShoppingListItem item) async {
    try {
      final updated = await _service.toggleItemChecked(_list!.id, item);
      _handleItemUpdated(updated);
    } catch (e) {
      // Show error snackbar
    }
  }

  @override
  void dispose() {
    _itemAddedSub?.cancel();
    _itemUpdatedSub?.cancel();
    _itemRemovedSub?.cancel();
    _presenceSub?.cancel();
    _syncSub?.cancel();
    _connectionSub?.cancel();
    _expandController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        widget.child,
        if (widget.listId != null) _buildFloatingWidget(),
      ],
    );
  }

  Widget _buildFloatingWidget() {
    return Positioned(
      right: 16,
      bottom: 16 + MediaQuery.of(context).viewPadding.bottom,
      child: AnimatedBuilder(
        animation: _expandAnimation,
        builder: (context, child) {
          return Container(
            width: _isExpanded ? 320 : null,
            constraints: BoxConstraints(
              maxHeight:
                  _isExpanded ? MediaQuery.of(context).size.height * 0.6 : 56,
            ),
            decoration: BoxDecoration(
              color: AppColors.cardBackground,
              borderRadius: BorderRadius.circular(_isExpanded ? 16 : 28),
              boxShadow: [
                BoxShadow(
                  color: AppColors.shadow,
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: _isExpanded ? _buildExpandedContent() : _buildCollapsedFab(),
          );
        },
      ),
    );
  }

  Widget _buildCollapsedFab() {
    final uncheckedCount = _list?.uncheckedCount ?? 0;
    final hasUrgent = _list?.hasUrgentItems ?? false;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: _toggleExpanded,
        borderRadius: BorderRadius.circular(28),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Stack(
                children: [
                  Icon(
                    Icons.shopping_cart,
                    color: hasUrgent ? AppColors.warning : AppColors.chocolate,
                  ),
                  if (uncheckedCount > 0)
                    Positioned(
                      right: -4,
                      top: -4,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: hasUrgent
                              ? AppColors.warning
                              : AppColors.chocolate,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        constraints: const BoxConstraints(
                          minWidth: 18,
                          minHeight: 18,
                        ),
                        child: Text(
                          uncheckedCount > 99 ? '99+' : uncheckedCount.toString(),
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AppColors.warmWhite,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                ],
              ),
              if (_onlineUsers.isNotEmpty) ...[
                const SizedBox(width: 8),
                MemberPresence(
                  onlineUsers: _onlineUsers,
                  maxVisible: 2,
                  avatarSize: 24,
                ),
              ],
              if (_connectionState == WebSocketState.connecting)
                const Padding(
                  padding: EdgeInsets.only(left: 8),
                  child: SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor:
                          AlwaysStoppedAnimation<Color>(AppColors.hazelnut),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildExpandedContent() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildHeader(),
        const Divider(height: 1),
        if (_isLoading)
          const Padding(
            padding: EdgeInsets.all(24),
            child: CircularProgressIndicator(),
          )
        else if (_error != null)
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              _error!,
              style: const TextStyle(color: AppColors.error),
            ),
          )
        else
          Flexible(child: _buildItemList()),
        const Divider(height: 1),
        _buildFooter(),
      ],
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _list?.name ?? 'Shopping List',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                if (_list != null)
                  Text(
                    '${_list!.uncheckedCount} items remaining',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textSecondary,
                    ),
                  ),
              ],
            ),
          ),
          if (_onlineUsers.isNotEmpty)
            MemberPresence(
              onlineUsers: _onlineUsers,
              maxVisible: 3,
              avatarSize: 24,
            ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: _toggleExpanded,
            icon: const Icon(Icons.close),
            iconSize: 20,
            color: AppColors.textSecondary,
            visualDensity: VisualDensity.compact,
          ),
        ],
      ),
    );
  }

  Widget _buildItemList() {
    if (_list == null || _list!.items.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(
          child: Text(
            'No items yet',
            style: TextStyle(color: AppColors.textTertiary),
          ),
        ),
      );
    }

    // Split into unchecked and checked
    final unchecked = _list!.items.where((i) => !i.isChecked).toList();
    final checked = _list!.items.where((i) => i.isChecked).toList();

    // Sort unchecked by urgency
    unchecked.sort((a, b) =>
        a.urgencyLevel.sortPriority.compareTo(b.urgencyLevel.sortPriority));

    return ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.symmetric(vertical: 8),
      children: [
        for (final item in unchecked)
          ShoppingListItemTile(
            item: item,
            compact: true,
            onChecked: (_) => _toggleItemChecked(item),
          ),
        if (checked.isNotEmpty) ...[
          ShoppingListSection(
            title: 'COMPLETED',
            itemCount: checked.length,
          ),
          for (final item in checked)
            ShoppingListItemTile(
              item: item,
              compact: true,
              showUrgency: false,
              onChecked: (_) => _toggleItemChecked(item),
            ),
        ],
      ],
    );
  }

  Widget _buildFooter() {
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          Expanded(
            child: TextButton.icon(
              onPressed: () {
                // TODO: Open add item dialog
              },
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add Item'),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.chocolate,
              ),
            ),
          ),
          if (_list?.isShared == true)
            IconButton(
              onPressed: () {
                // TODO: Show share sheet
              },
              icon: const Icon(Icons.share),
              iconSize: 20,
              color: AppColors.textSecondary,
            ),
        ],
      ),
    );
  }
}
