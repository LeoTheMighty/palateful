import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'home_selection_controller.dart';

/// Alternate AppBar rendered while `HomeSelectionState.isActive` is
/// true. Leading X (exit), title "{N} selected", no trailing actions
/// in v1 — matches the locked spec in the epic.
class SelectionAppBar extends ConsumerWidget
    implements PreferredSizeWidget {
  const SelectionAppBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(homeSelectionProvider);
    return AppBar(
      leading: IconButton(
        icon: const Icon(Icons.close),
        tooltip: 'Exit selection',
        onPressed: () =>
            ref.read(homeSelectionProvider.notifier).exit(),
      ),
      title: Text('${state.totalSelected} selected'),
    );
  }
}
