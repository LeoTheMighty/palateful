import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/state/mutation_failure_copy.dart';
import '../../core/state/mutation_snackbar.dart';
import '../../services/share_service.dart';
import '../../core/services/error_reporter.dart';
import '../../shared/widgets/error_banner.dart';
import '../../shared/widgets/free_forever_chip.dart';
import 'services/recipe_book_service.dart';

class RecipeBookMembersScreen extends StatefulWidget {
  final String recipeBookId;
  final String userRole;

  const RecipeBookMembersScreen({
    super.key,
    required this.recipeBookId,
    required this.userRole,
  });

  @override
  State<RecipeBookMembersScreen> createState() => _RecipeBookMembersScreenState();
}

class _RecipeBookMembersScreenState extends State<RecipeBookMembersScreen> {
  final _apiClient = getIt<ApiClient>();
  final _bookService = getIt<RecipeBookService>();
  List<dynamic> _members = [];
  bool _isLoading = true;
  String? _error;
  String? _errorDetail;

  @override
  void initState() {
    super.initState();
    _loadMembers();
  }

  Future<void> _loadMembers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final response = await _apiClient.getRecipeBook(widget.recipeBookId);
      if (mounted) {
        setState(() {
          _members = response.data['members'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Could not load members. Please try again.';
          _errorDetail = ErrorReporter.detail(e);
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _changeRole(String userId, String newRole) async {
    try {
      await _bookService.updateMemberRole(
        widget.recipeBookId,
        userId,
        newRole,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Role updated to $newRole')),
        );
        _loadMembers();
      }
    } catch (e) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.updateBookMemberRole,
          () => _changeRole(userId, newRole),
        );
      }
    }
  }

  Future<void> _removeMember(String userId, String memberName) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Member'),
        content: Text('Remove $memberName from this recipe book?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await _bookService.removeMember(widget.recipeBookId, userId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Member removed')),
        );
        _loadMembers();
      }
    } catch (e) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.removeBookMember,
          () => _removeMember(userId, memberName),
        );
      }
    }
  }

  Future<void> _showAddMemberDialog() async {
    final userIdController = TextEditingController();
    String selectedRole = 'editor';

    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              return AlertDialog(
                title: const Text('Add Member'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: userIdController,
                      decoration: const InputDecoration(
                        labelText: 'User ID',
                        hintText: 'Enter user ID',
                      ),
                      autofocus: true,
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: selectedRole,
                      decoration: const InputDecoration(labelText: 'Role'),
                      items: const [
                        DropdownMenuItem(value: 'editor', child: Text('Editor')),
                        DropdownMenuItem(value: 'viewer', child: Text('Viewer')),
                      ],
                      onChanged: (value) {
                        if (value != null) {
                          setDialogState(() => selectedRole = value);
                        }
                      },
                    ),
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: userIdController.text.trim().isEmpty
                        ? null
                        : () => Navigator.pop(context, true),
                    child: const Text('Add'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result == true && userIdController.text.trim().isNotEmpty) {
        await _bookService.addMember(
          widget.recipeBookId,
          userEmail: userIdController.text.trim(),
          role: selectedRole,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Member added')),
          );
          _loadMembers();
        }
      }
    } catch (e) {
      if (mounted) {
        showMutationFailureSnackbar(
          context,
          MutationType.addBookMember,
          _showAddMemberDialog,
        );
      }
    } finally {
      userIdController.dispose();
    }
  }

  Future<void> _showInviteBottomSheet() async {
    final inputController = TextEditingController();
    String selectedRole = 'viewer';
    String? generatedLink;
    bool isSending = false;
    bool isGenerating = false;

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return DefaultTabController(
              length: 2,
              child: Padding(
                padding: EdgeInsets.only(
                  bottom: MediaQuery.of(context).viewInsets.bottom,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const TabBar(
                      tabs: [
                        Tab(text: 'By username/email'),
                        Tab(text: 'Invite link'),
                      ],
                    ),
                    SizedBox(
                      height: 300,
                      child: TabBarView(
                        children: [
                          // Tab 1: Direct invite
                          Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                TextField(
                                  controller: inputController,
                                  decoration: const InputDecoration(
                                    labelText: 'Username or email',
                                    hintText: 'e.g. @alice or alice@example.com',
                                  ),
                                  autofocus: false,
                                  onChanged: (_) => setSheetState(() {}),
                                ),
                                const SizedBox(height: 12),
                                DropdownButtonFormField<String>(
                                  initialValue: selectedRole,
                                  decoration: const InputDecoration(labelText: 'Role'),
                                  items: const [
                                    DropdownMenuItem(value: 'editor', child: Text('Editor')),
                                    DropdownMenuItem(value: 'viewer', child: Text('Viewer')),
                                  ],
                                  onChanged: (value) {
                                    if (value != null) {
                                      setSheetState(() => selectedRole = value);
                                    }
                                  },
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton(
                                  onPressed: inputController.text.trim().isEmpty || isSending
                                      ? null
                                      : () async {
                                          setSheetState(() => isSending = true);
                                          final input = inputController.text.trim();
                                          final isEmail = input.contains('@') && input.contains('.');
                                          final data = {
                                            'resource_type': 'recipe_book',
                                            'resource_id': widget.recipeBookId,
                                            'role_offered': selectedRole,
                                            if (isEmail) 'to_email': input
                                            else 'to_username': input.replaceFirst('@', ''),
                                          };
                                          final sheetNavigator = Navigator.of(sheetContext);
                                          final scaffoldMessenger = ScaffoldMessenger.of(context);
                                          try {
                                            await _apiClient.sendInvitation(data);
                                            if (mounted) {
                                              sheetNavigator.pop();
                                              scaffoldMessenger.showSnackBar(
                                                const SnackBar(content: Text('Invitation sent')),
                                              );
                                            }
                                          } catch (e) {
                                            setSheetState(() => isSending = false);
                                            if (mounted) {
                                              scaffoldMessenger.showSnackBar(
                                                const SnackBar(content: Text('Could not send invitation. The user may not exist or is already a member.')),
                                              );
                                            }
                                          }
                                        },
                                  child: isSending
                                      ? const SizedBox(
                                          height: 16,
                                          width: 16,
                                          child: CircularProgressIndicator(strokeWidth: 2),
                                        )
                                      : const Text('Send Invite'),
                                ),
                              ],
                            ),
                          ),

                          // Tab 2: Invite link
                          Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                if (generatedLink == null) ...[
                                  const Text(
                                    'Generate a shareable link. Anyone with the link can join as viewer.',
                                    textAlign: TextAlign.center,
                                  ),
                                  const SizedBox(height: 16),
                                  ElevatedButton(
                                    onPressed: isGenerating
                                        ? null
                                        : () async {
                                            setSheetState(() => isGenerating = true);
                                            try {
                                              final response = await _apiClient.createInviteLink({
                                                'resource_type': 'recipe_book',
                                                'resource_id': widget.recipeBookId,
                                                'role_offered': 'viewer',
                                              });
                                              final link = response.data['deep_link'] as String?;
                                              setSheetState(() {
                                                generatedLink = link;
                                                isGenerating = false;
                                              });
                                            } catch (e) {
                                              setSheetState(() => isGenerating = false);
                                            }
                                          },
                                    child: isGenerating
                                        ? const SizedBox(
                                            height: 16,
                                            width: 16,
                                            child: CircularProgressIndicator(strokeWidth: 2),
                                          )
                                        : const Text('Generate Link'),
                                  ),
                                ] else ...[
                                  Container(
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: Theme.of(context).colorScheme.surfaceContainerHighest,
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      generatedLink!,
                                      style: Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: OutlinedButton.icon(
                                          onPressed: () {
                                            Clipboard.setData(ClipboardData(text: generatedLink!));
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              const SnackBar(content: Text('Link copied')),
                                            );
                                          },
                                          icon: const Icon(Icons.copy),
                                          label: const Text('Copy'),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: ElevatedButton.icon(
                                          onPressed: () {
                                            Share.share(
                                              generatedLink!,
                                              sharePositionOrigin: ShareService.originFrom(context),
                                            );
                                          },
                                          icon: const Icon(Icons.share),
                                          label: const Text('Share'),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      child: Row(
                        children: const [
                          Expanded(child: FreeForeverChip.household()),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );

    inputController.dispose();
  }

  Color _roleChipColor(BuildContext context, String role) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (role) {
      case 'owner':
        return colorScheme.primaryContainer;
      case 'editor':
        return colorScheme.tertiaryContainer;
      default:
        return colorScheme.surfaceContainerHighest;
    }
  }

  Color _roleChipTextColor(BuildContext context, String role) {
    final colorScheme = Theme.of(context).colorScheme;
    switch (role) {
      case 'owner':
        return colorScheme.onPrimaryContainer;
      case 'editor':
        return colorScheme.onTertiaryContainer;
      default:
        return colorScheme.onSurfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colorScheme = Theme.of(context).colorScheme;
    final isOwner = widget.userRole == 'owner';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Members'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
        actions: [
          if (isOwner)
            TextButton.icon(
              onPressed: _showInviteBottomSheet,
              icon: const Icon(Icons.person_add_alt_1),
              label: const Text('Invite'),
            ),
        ],
      ),
      floatingActionButton: isOwner
          ? FloatingActionButton(
              onPressed: _showAddMemberDialog,
              child: const Icon(Icons.person_add),
            )
          : null,
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        ErrorBanner(message: _error!, detail: _errorDetail),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadMembers,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: _members.length,
                  separatorBuilder: (context, index) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final member = _members[index];
                    final userId = member['user_id'] as String? ?? '';
                    final name = member['name'] as String? ?? 'Unknown';
                    final role = member['role'] as String? ?? 'viewer';
                    final isOwnerMember = role == 'owner';

                    return ListTile(
                      leading: CircleAvatar(
                        backgroundColor: colorScheme.surfaceContainerHighest,
                        child: Icon(Icons.person, color: colorScheme.onSurfaceVariant),
                      ),
                      title: Text(name, style: textTheme.bodyLarge),
                      subtitle: Container(
                        margin: const EdgeInsets.only(top: 4),
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: _roleChipColor(context, role),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          role,
                          style: textTheme.labelSmall?.copyWith(
                            color: _roleChipTextColor(context, role),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      trailing: isOwner && !isOwnerMember
                          ? PopupMenuButton<String>(
                              onSelected: (value) {
                                if (value == 'make_editor') {
                                  _changeRole(userId, 'editor');
                                } else if (value == 'make_viewer') {
                                  _changeRole(userId, 'viewer');
                                } else if (value == 'remove') {
                                  _removeMember(userId, name);
                                }
                              },
                              itemBuilder: (context) => [
                                if (role != 'editor')
                                  const PopupMenuItem(
                                    value: 'make_editor',
                                    child: Text('Change to Editor'),
                                  ),
                                if (role != 'viewer')
                                  const PopupMenuItem(
                                    value: 'make_viewer',
                                    child: Text('Change to Viewer'),
                                  ),
                                PopupMenuItem(
                                  value: 'remove',
                                  child: Text(
                                    'Remove',
                                    style: TextStyle(color: colorScheme.error),
                                  ),
                                ),
                              ],
                            )
                          : null,
                    );
                  },
                ),
    );
  }
}
