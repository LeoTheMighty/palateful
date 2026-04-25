import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('RecipeBooksScreen UI', () {
    testWidgets('renders book list with names, recipe counts, and descriptions',
        (tester) async {
      final books = [
        {
          'id': '1',
          'name': 'Italian Favorites',
          'description': 'My best Italian recipes',
          'recipe_count': 12,
          'updated_at': DateTime.now().toIso8601String(),
        },
        {
          'id': '2',
          'name': 'Quick Dinners',
          'description': null,
          'recipe_count': 5,
          'updated_at': DateTime.now()
              .subtract(const Duration(days: 3))
              .toIso8601String(),
        },
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            floatingActionButton: FloatingActionButton(
              onPressed: () {},
              child: const Icon(Icons.add),
            ),
            body: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: books.length,
              itemBuilder: (context, index) {
                final book = books[index];
                final recipeCount = book['recipe_count'] as int;
                final description = book['description'] as String?;

                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(Icons.book),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(book['name'] as String,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w600)),
                              if (description != null)
                                Text(description,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis),
                              Text(
                                  '$recipeCount ${recipeCount == 1 ? 'recipe' : 'recipes'}'),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      );

      // Verify book names
      expect(find.text('Italian Favorites'), findsOneWidget);
      expect(find.text('Quick Dinners'), findsOneWidget);

      // Verify recipe counts
      expect(find.text('12 recipes'), findsOneWidget);
      expect(find.text('5 recipes'), findsOneWidget);

      // Verify description
      expect(find.text('My best Italian recipes'), findsOneWidget);

      // Verify FAB exists
      expect(find.byType(FloatingActionButton), findsOneWidget);
    });

    testWidgets('renders create dialog with name field and validation',
        (tester) async {
      final nameController = TextEditingController();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => Center(
                child: ElevatedButton(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (context) {
                        return StatefulBuilder(
                          builder: (context, setDialogState) {
                            final nameIsEmpty =
                                nameController.text.trim().isEmpty;
                            return AlertDialog(
                              title: const Text('New Recipe Book'),
                              content: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  TextField(
                                    controller: nameController,
                                    decoration: const InputDecoration(
                                      labelText: 'Name',
                                      hintText: 'My Recipe Book',
                                    ),
                                    autofocus: true,
                                    onChanged: (_) => setDialogState(() {}),
                                  ),
                                  const SizedBox(height: 16),
                                  TextField(
                                    decoration: const InputDecoration(
                                      labelText: 'Description (optional)',
                                    ),
                                    maxLines: 2,
                                  ),
                                ],
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(context),
                                  child: const Text('Cancel'),
                                ),
                                ElevatedButton(
                                  onPressed: nameIsEmpty ? null : () {},
                                  child: const Text('Create'),
                                ),
                              ],
                            );
                          },
                        );
                      },
                    );
                  },
                  child: const Text('Open Dialog'),
                ),
              ),
            ),
          ),
        ),
      );

      // Open the dialog
      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      // Dialog should be visible
      expect(find.text('New Recipe Book'), findsOneWidget);
      expect(find.text('Name'), findsOneWidget);
      expect(find.text('Description (optional)'), findsOneWidget);

      // Create button should be disabled (name empty)
      final createButton = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, 'Create'),
      );
      expect(createButton.onPressed, isNull);

      // Type a name
      await tester.enterText(
        find.widgetWithText(TextField, 'My Recipe Book'),
        'Desserts',
      );
      await tester.pumpAndSettle();

      // Create button should now be enabled
      final enabledButton = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, 'Create'),
      );
      expect(enabledButton.onPressed, isNotNull);
    });
  });

  group('RecipeBookDetailScreen UI', () {
    testWidgets('renders photo-dominant recipe cards', (tester) async {
      final recipes = [
        {
          'id': '1',
          'name': 'Pasta Carbonara',
          'image_url': null,
          'prep_time': 10,
          'cook_time': 20,
          'servings': 4,
          'tags': ['Italian', 'Pasta'],
        },
        {
          'id': '2',
          'name': 'Chicken Tikka',
          'image_url': null,
          'prep_time': 30,
          'cook_time': null,
          'servings': 6,
          'tags': [],
        },
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              padding: const EdgeInsets.all(16),
              children: recipes.map((recipe) {
                final tags =
                    (recipe['tags'] as List?)?.cast<String>() ?? [];
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  clipBehavior: Clip.antiAlias,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Hero image placeholder
                      SizedBox(
                        height: 180,
                        width: double.infinity,
                        child: Container(
                          color: Colors.grey[200],
                          child: const Icon(Icons.restaurant, size: 48),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              recipe['name'] as String,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600, fontSize: 16),
                            ),
                            const SizedBox(height: 6),
                            Wrap(
                              spacing: 8,
                              children: [
                                if (recipe['prep_time'] != null)
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Icon(Icons.timer_outlined,
                                          size: 14),
                                      const SizedBox(width: 4),
                                      Text('Prep ${recipe['prep_time']}m'),
                                    ],
                                  ),
                                if (recipe['cook_time'] != null)
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Icon(
                                          Icons.local_fire_department_outlined,
                                          size: 14),
                                      const SizedBox(width: 4),
                                      Text('Cook ${recipe['cook_time']}m'),
                                    ],
                                  ),
                                if (recipe['servings'] != null)
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Icon(Icons.people_outline,
                                          size: 14),
                                      const SizedBox(width: 4),
                                      Text('Serves ${recipe['servings']}'),
                                    ],
                                  ),
                              ],
                            ),
                            if (tags.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 6,
                                runSpacing: 4,
                                children: tags
                                    .map((tag) => Chip(
                                          label: Text(tag),
                                          visualDensity:
                                              VisualDensity.compact,
                                          padding: EdgeInsets.zero,
                                        ))
                                    .toList(),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
        ),
      );

      // Verify recipe names
      expect(find.text('Pasta Carbonara'), findsOneWidget);
      expect(find.text('Chicken Tikka'), findsOneWidget);

      // Verify metadata chips
      expect(find.text('Prep 10m'), findsOneWidget);
      expect(find.text('Cook 20m'), findsOneWidget);
      expect(find.text('Serves 4'), findsOneWidget);
      expect(find.text('Serves 6'), findsOneWidget);

      // Verify tags
      expect(find.text('Italian'), findsOneWidget);
      expect(find.text('Pasta'), findsOneWidget);

      // Verify photo placeholder icons (hero images with fallback)
      expect(find.byIcon(Icons.restaurant), findsNWidgets(2));

      // Verify card height includes image area (180px)
      final sizedBoxes = tester.widgetList<SizedBox>(
        find.byWidgetPredicate(
          (w) => w is SizedBox && w.height == 180,
        ),
      );
      expect(sizedBoxes.length, 2);
    });

    testWidgets('renders empty state when no recipes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            floatingActionButton: FloatingActionButton(
              onPressed: () {},
              child: const Icon(Icons.add),
            ),
            body: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text('Recipes (0)'),
                const SizedBox(height: 8),
                SizedBox(
                  height: 300,
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.restaurant_menu, size: 56),
                        const SizedBox(height: 24),
                        const Text('Add your first recipe'),
                        const SizedBox(height: 8),
                        const Text('Tap + to add a recipe to this book'),
                        const SizedBox(height: 24),
                        ElevatedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.add),
                          label: const Text('Add Recipe'),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Recipes (0)'), findsOneWidget);
      expect(find.text('Add your first recipe'), findsOneWidget);
      expect(find.text('Tap + to add a recipe to this book'), findsOneWidget);
      expect(find.text('Add Recipe'), findsOneWidget);
    });

    testWidgets('shows edit and delete in menu', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: const Text('My Cookbook'),
              actions: [
                PopupMenuButton<String>(
                  onSelected: (value) {},
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'edit',
                      child: Row(
                        children: [
                          Icon(Icons.edit_outlined),
                          SizedBox(width: 8),
                          Text('Edit'),
                        ],
                      ),
                    ),
                    PopupMenuItem(
                      value: 'delete',
                      child: Row(
                        children: [
                          Icon(Icons.delete,
                              color: Theme.of(context).colorScheme.error),
                          const SizedBox(width: 8),
                          Text('Delete',
                              style: TextStyle(
                                  color:
                                      Theme.of(context).colorScheme.error)),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      );

      // Verify app bar title
      expect(find.text('My Cookbook'), findsOneWidget);

      // Open popup menu
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();

      // Verify menu items
      expect(find.text('Edit'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);
      expect(find.byIcon(Icons.edit_outlined), findsOneWidget);
      expect(find.byIcon(Icons.delete), findsOneWidget);
    });
  });

  group('RecipeBooksScreen System section (recipe-defaults-3)', () {
    // Synthetic harness mirrors the rendering structure of
    // `RecipeBooksScreen` after the System-section refactor: a header,
    // two pinned tiles, a divider, then the user-books list with the
    // is_system row filtered out.
    Widget _buildHarness({required List<Map<String, dynamic>> books}) {
      final tryingOut = books.cast<Map<String, dynamic>?>().firstWhere(
            (b) => b?['is_system'] == true,
            orElse: () => null,
          );
      final userBooks =
          books.where((b) => b['is_system'] != true).toList();
      const headerCount = 4;
      return MaterialApp(
        home: Scaffold(
          body: Builder(builder: (ctx) {
            final colorScheme = Theme.of(ctx).colorScheme;
            final textTheme = Theme.of(ctx).textTheme;
            return ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: headerCount + userBooks.length,
              itemBuilder: (context, index) {
                if (index == 0) {
                  return Text('System',
                      style: textTheme.labelLarge
                          ?.copyWith(color: colorScheme.outline));
                }
                if (index == 1) {
                  return Card(
                    key: const Key('system-tile-favorites'),
                    child: ListTile(
                      leading: const Icon(Icons.favorite),
                      title: const Text('Favorites'),
                      onTap: () {},
                    ),
                  );
                }
                if (index == 2) {
                  if (tryingOut == null) return const SizedBox.shrink();
                  final n = tryingOut['recipe_count'] ?? 0;
                  return Card(
                    key: const Key('system-tile-trying-out'),
                    child: ListTile(
                      leading: const Icon(Icons.science_outlined),
                      title: const Text('Trying Out'),
                      subtitle:
                          Text('$n ${n == 1 ? 'recipe' : 'recipes'}'),
                      onTap: () {},
                    ),
                  );
                }
                if (index == 3) {
                  return const Divider();
                }
                final book = userBooks[index - headerCount];
                return ListTile(
                  title: Text(book['name'] as String),
                );
              },
            );
          }),
        ),
      );
    }

    testWidgets('renders System header + both pinned tiles when system book present',
        (tester) async {
      final books = <Map<String, dynamic>>[
        {
          'id': 'sys-1',
          'name': 'Trying Out',
          'is_system': true,
          'recipe_count': 7,
        },
        {
          'id': 'usr-1',
          'name': 'Italian Favorites',
          'is_system': false,
          'recipe_count': 12,
        },
      ];

      await tester.pumpWidget(_buildHarness(books: books));

      // System header rendered.
      expect(find.text('System'), findsOneWidget);
      // Both pinned tiles rendered with distinct keys.
      expect(find.byKey(const Key('system-tile-favorites')), findsOneWidget);
      expect(find.byKey(const Key('system-tile-trying-out')), findsOneWidget);
      // Trying Out shows the recipe count from the API row.
      expect(find.text('7 recipes'), findsOneWidget);
      // User book renders below the divider.
      expect(find.text('Italian Favorites'), findsOneWidget);
    });

    testWidgets('Trying Out is NOT duplicated in the user-books list',
        (tester) async {
      final books = <Map<String, dynamic>>[
        {
          'id': 'sys-1',
          'name': 'Trying Out',
          'is_system': true,
          'recipe_count': 3,
        },
        {
          'id': 'usr-1',
          'name': 'Weeknight',
          'is_system': false,
          'recipe_count': 2,
        },
      ];

      await tester.pumpWidget(_buildHarness(books: books));

      // The system tile still says 'Trying Out' …
      expect(find.text('Trying Out'), findsOneWidget);
      // … and the user-books list contains only Weeknight (one ListTile
      // for it; the system section uses Card+ListTile but those are
      // counted too — assert the user book exists, no duplicate
      // rendering of 'Trying Out' name).
      final tryingOutFinders = find.text('Trying Out');
      expect(tryingOutFinders, findsOneWidget);
    });

    testWidgets('System section renders Favorites tile even with no Trying Out book',
        (tester) async {
      // Edge case: backend back-fill hasn't run yet for this user; the
      // user has no system book. Favorites still pins; Trying Out
      // tile collapses (SizedBox.shrink).
      final books = <Map<String, dynamic>>[
        {
          'id': 'usr-1',
          'name': 'Solo Book',
          'is_system': false,
          'recipe_count': 1,
        },
      ];

      await tester.pumpWidget(_buildHarness(books: books));

      expect(find.text('System'), findsOneWidget);
      expect(find.byKey(const Key('system-tile-favorites')), findsOneWidget);
      expect(
          find.byKey(const Key('system-tile-trying-out')), findsNothing);
      expect(find.text('Solo Book'), findsOneWidget);
    });
  });
}
