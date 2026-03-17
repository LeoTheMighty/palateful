import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../core/di/injection.dart';
import '../../../core/theme/app_colors.dart';
import '../models/shopping_list.dart';
import '../models/shopping_list_item.dart';
import '../services/shopping_cart_service.dart';
import '../widgets/member_presence.dart';
import '../widgets/shopping_list_item_tile.dart';

/// Full screen shopping list view.
class ShoppingListScreen extends StatefulWidget {
  final String listId;

  const ShoppingListScreen({
    super.key,
    required this.listId,
  });

  @override
  State<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends State<ShoppingListScreen> {
  final ShoppingCartService _service = getIt<ShoppingCartService>();

  ShoppingList? _list;
  List<OnlineUser> _onlineUsers = [];
  bool _isLoading = true;
  String? _error;
  bool _showChecked = true;

  // Stream subscriptions
  StreamSubscription? _itemAddedSub;
  StreamSubscription? _itemUpdatedSub;
  StreamSubscription? _itemRemovedSub;
  StreamSubscription? _presenceSub;
  StreamSubscription? _syncSub;

  final _addItemController = TextEditingController();
  final _addItemFocus = FocusNode();

  @override
  void initState() {
    super.initState();
    _setupSubscriptions();
    _loadList();
  }

  void _setupSubscriptions() {
    _itemAddedSub = _service.onItemAdded.listen(_handleItemAdded);
    _itemUpdatedSub = _service.onItemUpdated.listen(_handleItemUpdated);
    _itemRemovedSub = _service.onItemRemoved.listen(_handleItemRemoved);
    _presenceSub = _service.onPresenceUpdate.listen(_handlePresenceUpdate);
    _syncSub = _service.onSync.listen(_handleSync);
  }

  Future<void> _loadList() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final list = await _service.getShoppingList(widget.listId);
      if (mounted) {
        setState(() {
          _list = list;
          _isLoading = false;
        });
        _service.connectWebSocket(widget.listId);
        _service.updatePresence('shopping');
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
      _list = _list!.copyWith(items: [..._list!.items, item]);
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
    setState(() {
      _onlineUsers = sync.onlineUsers
          .map((id) => OnlineUser(id: id, timestamp: DateTime.now()))
          .toList();
    });
  }

  Future<void> _toggleItemChecked(ShoppingListItem item) async {
    HapticFeedback.lightImpact();
    try {
      final updated = await _service.toggleItemChecked(_list!.id, item);
      _handleItemUpdated(updated);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to update item')),
        );
      }
    }
  }

  Future<void> _addItem() async {
    final name = _addItemController.text.trim();
    if (name.isEmpty || _list == null) return;

    _addItemController.clear();
    HapticFeedback.mediumImpact();

    try {
      await _service.addItem(_list!.id, name: name);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to add item')),
        );
      }
    }
  }

  Future<void> _deleteItem(ShoppingListItem item) async {
    HapticFeedback.mediumImpact();
    try {
      await _service.deleteItem(_list!.id, item.id);
      _handleItemRemoved(item.id);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to delete item')),
        );
      }
    }
  }

  Future<void> _shareList() async {
    if (_list == null) return;
    try {
      final shareCode = await _service.shareList(_list!.id);
      if (mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Share Shopping List'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Share this code with others:'),
                const SizedBox(height: 16),
                SelectableText(
                  shareCode,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 4,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: shareCode));
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Code copied to clipboard')),
                  );
                },
                child: const Text('Copy'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Done'),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to generate share code')),
        );
      }
    }
  }

  @override
  void dispose() {
    _itemAddedSub?.cancel();
    _itemUpdatedSub?.cancel();
    _itemRemovedSub?.cancel();
    _presenceSub?.cancel();
    _syncSub?.cancel();
    _addItemController.dispose();
    _addItemFocus.dispose();
    _service.updatePresence('online');
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.cream,
      appBar: _buildAppBar(),
      body: _buildBody(),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: AppColors.cream,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back),
        onPressed: () => context.pop(),
      ),
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _list?.name ?? 'Shopping List',
            style: const TextStyle(
              fontSize: 18,
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
      actions: [
        if (_onlineUsers.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: MemberPresence(
              onlineUsers: _onlineUsers,
              maxVisible: 3,
              avatarSize: 28,
            ),
          ),
        if (_list?.isShared == true || _list != null)
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: _shareList,
            tooltip: 'Share List',
          ),
        PopupMenuButton<String>(
          onSelected: (value) {
            switch (value) {
              case 'clear_checked':
                _clearCheckedItems();
                break;
              case 'toggle_checked':
                setState(() {
                  _showChecked = !_showChecked;
                });
                break;
            }
          },
          itemBuilder: (context) => [
            PopupMenuItem(
              value: 'toggle_checked',
              child: Row(
                children: [
                  Icon(
                    _showChecked ? Icons.visibility_off : Icons.visibility,
                    size: 20,
                  ),
                  const SizedBox(width: 12),
                  Text(_showChecked ? 'Hide Completed' : 'Show Completed'),
                ],
              ),
            ),
            const PopupMenuItem(
              value: 'clear_checked',
              child: Row(
                children: [
                  Icon(Icons.delete_sweep, size: 20),
                  SizedBox(width: 12),
                  Text('Clear Completed'),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  void _clearCheckedItems() {
    if (_list == null) return;
    final checkedItems = _list!.items.where((i) => i.isChecked).toList();
    for (final item in checkedItems) {
      _deleteItem(item);
    }
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: const TextStyle(color: AppColors.error)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadList,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        Expanded(child: _buildItemList()),
        _buildAddItemBar(),
      ],
    );
  }

  Widget _buildItemList() {
    if (_list == null || _list!.items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.shopping_cart_outlined,
              size: 64,
              color: AppColors.textDisabled,
            ),
            const SizedBox(height: 16),
            const Text(
              'Your shopping list is empty',
              style: TextStyle(
                fontSize: 16,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Add items below to get started',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      );
    }

    final unchecked = _list!.items.where((i) => !i.isChecked).toList();
    final checked = _list!.items.where((i) => i.isChecked).toList();

    // Sort unchecked by urgency then name
    unchecked.sort((a, b) {
      final urgencyCompare =
          a.urgencyLevel.sortPriority.compareTo(b.urgencyLevel.sortPriority);
      if (urgencyCompare != 0) return urgencyCompare;
      return a.name.compareTo(b.name);
    });

    return RefreshIndicator(
      onRefresh: _loadList,
      color: AppColors.chocolate,
      child: ListView(
        padding: const EdgeInsets.only(bottom: 100),
        children: [
          // Urgency header if there are urgent items
          if (_list!.hasUrgentItems)
            Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.warningLight,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.schedule, color: AppColors.warningDark),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Some items need to be purchased soon!',
                      style: const TextStyle(color: AppColors.warningDark),
                    ),
                  ),
                ],
              ),
            ),

          // Unchecked items
          for (final item in unchecked)
            Dismissible(
              key: Key(item.id),
              direction: DismissDirection.endToStart,
              background: Container(
                alignment: Alignment.centerRight,
                padding: const EdgeInsets.only(right: 16),
                color: AppColors.error,
                child: const Icon(Icons.delete, color: Colors.white),
              ),
              onDismissed: (_) => _deleteItem(item),
              child: ShoppingListItemTile(
                item: item,
                onChecked: (_) => _toggleItemChecked(item),
                onLongPress: () => _showItemOptions(item),
              ),
            ),

          // Checked items section
          if (checked.isNotEmpty && _showChecked) ...[
            ShoppingListSection(
              title: 'COMPLETED',
              itemCount: checked.length,
              trailing: TextButton(
                onPressed: _clearCheckedItems,
                child: const Text(
                  'Clear All',
                  style: TextStyle(fontSize: 12),
                ),
              ),
            ),
            for (final item in checked)
              Dismissible(
                key: Key(item.id),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: 16),
                  color: AppColors.error,
                  child: const Icon(Icons.delete, color: Colors.white),
                ),
                onDismissed: (_) => _deleteItem(item),
                child: ShoppingListItemTile(
                  item: item,
                  showUrgency: false,
                  onChecked: (_) => _toggleItemChecked(item),
                ),
              ),
          ],
        ],
      ),
    );
  }

  void _showItemOptions(ShoppingListItem item) {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit),
              title: const Text('Edit Item'),
              onTap: () {
                Navigator.pop(context);
                // TODO: Show edit dialog
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete, color: AppColors.error),
              title: const Text('Delete Item',
                  style: TextStyle(color: AppColors.error)),
              onTap: () {
                Navigator.pop(context);
                _deleteItem(item);
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddItemBar() {
    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 12,
        bottom: 12 + MediaQuery.of(context).viewPadding.bottom,
      ),
      decoration: BoxDecoration(
        color: AppColors.warmWhite,
        boxShadow: [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _addItemController,
              focusNode: _addItemFocus,
              decoration: InputDecoration(
                hintText: 'Add item...',
                hintStyle: const TextStyle(color: AppColors.textTertiary),
                filled: true,
                fillColor: AppColors.beige,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _addItem(),
            ),
          ),
          const SizedBox(width: 12),
          Container(
            decoration: BoxDecoration(
              color: AppColors.chocolate,
              borderRadius: BorderRadius.circular(12),
            ),
            child: IconButton(
              onPressed: _addItem,
              icon: const Icon(Icons.add),
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}
