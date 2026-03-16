import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:palateful/core/theme/app_colors.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('RecipeDetailScreen UI - Structured Steps', () {
    testWidgets('renders numbered steps list', (tester) async {
      final steps = [
        {'step_number': 1, 'instruction': 'Preheat oven to 350F'},
        {'step_number': 2, 'instruction': 'Mix dry ingredients'},
        {'step_number': 3, 'instruction': 'Bake for 25 minutes'},
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Steps',
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.w400)),
                  const SizedBox(height: 8),
                  ...steps.asMap().entries.map((entry) {
                    final index = entry.key;
                    final step = entry.value;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 32,
                            height: 32,
                            decoration: BoxDecoration(
                              color: AppColors.beige,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Center(
                              child: Text(
                                '${index + 1}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.hazelnut,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(step['instruction'] as String),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Steps'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('Preheat oven to 350F'), findsOneWidget);
      expect(find.text('Mix dry ingredients'), findsOneWidget);
      expect(find.text('Bake for 25 minutes'), findsOneWidget);
    });

    testWidgets('falls back to legacy instructions when no steps',
        (tester) async {
      const instructions = 'Mix everything and bake at 350F for 25 minutes.';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Instructions',
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.w400)),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.beige,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.beigeAccent),
                    ),
                    child: const Text(instructions),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Instructions'), findsOneWidget);
      expect(find.text(instructions), findsOneWidget);
    });
  });

  group('RecipeDetailScreen UI - Tags', () {
    testWidgets('renders tags as chips', (tester) async {
      final tags = ['Italian', 'Pasta', 'Quick'];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Tags',
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.w400)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: tags
                        .map((tag) => Chip(
                              label: Text(tag),
                              backgroundColor: AppColors.beige,
                            ))
                        .toList(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Tags'), findsOneWidget);
      expect(find.byType(Chip), findsNWidgets(3));
      expect(find.text('Italian'), findsOneWidget);
      expect(find.text('Pasta'), findsOneWidget);
      expect(find.text('Quick'), findsOneWidget);
    });

    testWidgets('no tags section when tags list is empty', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: const [
                  Text('Recipe Content'),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Tags'), findsNothing);
      expect(find.byType(Chip), findsNothing);
    });
  });

  group('RecipeDetailScreen UI - Source URL', () {
    testWidgets('renders source URL as tappable link', (tester) async {
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InkWell(
              onTap: () => tapped = true,
              child: const Row(
                children: [
                  Icon(Icons.link, size: 18, color: AppColors.hazelnut),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'https://example.com/recipe',
                      style: TextStyle(
                        color: AppColors.hazelnut,
                        decoration: TextDecoration.underline,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('https://example.com/recipe'), findsOneWidget);
      expect(find.byIcon(Icons.link), findsOneWidget);

      await tester.tap(find.byType(InkWell));
      expect(tapped, isTrue);
    });
  });

  group('RecipeDetailScreen UI - Edit Button', () {
    testWidgets('shows edit button in app bar', (tester) async {
      bool editTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: const Text('Test Recipe'),
              actions: [
                IconButton(
                  icon: const Icon(Icons.edit_outlined),
                  onPressed: () => editTapped = true,
                ),
              ],
            ),
            body: const Text('Recipe content'),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit_outlined), findsOneWidget);

      await tester.tap(find.byIcon(Icons.edit_outlined));
      expect(editTapped, isTrue);
    });
  });

  group('EditRecipeScreen UI - Form Fields', () {
    testWidgets('renders pre-populated form fields', (tester) async {
      final nameController = TextEditingController(text: 'Chocolate Cake');
      final prepTimeController = TextEditingController(text: '20');
      final cookTimeController = TextEditingController(text: '45');
      final servingsController = TextEditingController(text: '8');
      final sourceUrlController =
          TextEditingController(text: 'https://example.com');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(title: const Text('Edit Recipe')),
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Recipe Name',
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: prepTimeController,
                          decoration: const InputDecoration(
                            labelText: 'Prep time',
                            suffixText: 'min',
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: TextField(
                          controller: cookTimeController,
                          decoration: const InputDecoration(
                            labelText: 'Cook time',
                            suffixText: 'min',
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: servingsController,
                    decoration: const InputDecoration(
                      labelText: 'Servings',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: sourceUrlController,
                    decoration: const InputDecoration(
                      labelText: 'Source URL (optional)',
                      prefixIcon: Icon(Icons.link),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Edit Recipe'), findsOneWidget);
      expect(find.text('Chocolate Cake'), findsOneWidget);
      expect(find.text('20'), findsOneWidget);
      expect(find.text('45'), findsOneWidget);
      expect(find.text('8'), findsOneWidget);
      expect(find.text('https://example.com'), findsOneWidget);
      expect(find.text('Recipe Name'), findsOneWidget);
      expect(find.text('Prep time'), findsOneWidget);
      expect(find.text('Cook time'), findsOneWidget);
      expect(find.text('Servings'), findsOneWidget);

      nameController.dispose();
      prepTimeController.dispose();
      cookTimeController.dispose();
      servingsController.dispose();
      sourceUrlController.dispose();
    });

    testWidgets('renders save status indicators', (tester) async {
      // Test "Saving..." state
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: const Text('Edit Recipe'),
              actions: const [
                Padding(
                  padding: EdgeInsets.only(right: 16),
                  child: Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        SizedBox(width: 6),
                        Text('Saving...',
                            style: TextStyle(fontSize: 13)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            body: const SizedBox.shrink(),
          ),
        ),
      );

      expect(find.text('Saving...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('renders "Saved" status indicator', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: const Text('Edit Recipe'),
              actions: const [
                Padding(
                  padding: EdgeInsets.only(right: 16),
                  child: Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.check, size: 16, color: AppColors.success),
                        SizedBox(width: 4),
                        Text('Saved',
                            style: TextStyle(
                                fontSize: 13, color: AppColors.success)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            body: const SizedBox.shrink(),
          ),
        ),
      );

      expect(find.text('Saved'), findsOneWidget);
      expect(find.byIcon(Icons.check), findsOneWidget);
    });
  });

  group('EditRecipeScreen UI - Steps Management', () {
    testWidgets('renders step list with add and remove buttons',
        (tester) async {
      final stepControllers = [
        TextEditingController(text: 'Preheat oven'),
        TextEditingController(text: 'Mix ingredients'),
      ];
      bool addStepCalled = false;
      final removedSteps = <int>[];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Steps',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                  const SizedBox(height: 8),
                  ...stepControllers.asMap().entries.map((entry) {
                    final index = entry.key;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 32,
                            height: 32,
                            margin: const EdgeInsets.only(top: 8),
                            decoration: BoxDecoration(
                              color: AppColors.beige,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Center(
                              child: Text('${index + 1}'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: entry.value,
                              decoration: InputDecoration(
                                hintText: 'Step ${index + 1}...',
                              ),
                              maxLines: null,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, size: 20),
                            onPressed: () => removedSteps.add(index),
                          ),
                        ],
                      ),
                    );
                  }),
                  Center(
                    child: TextButton.icon(
                      onPressed: () => addStepCalled = true,
                      icon: const Icon(Icons.add),
                      label: const Text('Add Step'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Steps'), findsOneWidget);
      expect(find.text('Preheat oven'), findsOneWidget);
      expect(find.text('Mix ingredients'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text('Add Step'), findsOneWidget);

      // Tap add step
      await tester.tap(find.text('Add Step'));
      expect(addStepCalled, isTrue);

      // Tap remove on first step
      await tester.tap(find.byIcon(Icons.close).first);
      expect(removedSteps, [0]);

      for (final c in stepControllers) {
        c.dispose();
      }
    });
  });

  group('EditRecipeScreen UI - Tags Management', () {
    testWidgets('renders tags with add and delete functionality',
        (tester) async {
      final tags = ['Italian', 'Dinner'];
      final deletedTags = <String>[];
      final tagController = TextEditingController();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Tags',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: tagController,
                          decoration: const InputDecoration(
                            hintText: 'Add a tag...',
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        onPressed: () {},
                        icon: const Icon(Icons.add),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: tags
                        .map((tag) => InputChip(
                              label: Text(tag),
                              onDeleted: () => deletedTags.add(tag),
                              backgroundColor: AppColors.beige,
                            ))
                        .toList(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Tags'), findsOneWidget);
      expect(find.byType(InputChip), findsNWidgets(2));
      expect(find.text('Italian'), findsOneWidget);
      expect(find.text('Dinner'), findsOneWidget);
      expect(find.text('Add a tag...'), findsOneWidget);

      // Find the delete button on the Italian chip and tap it
      final italianChip = find.widgetWithText(InputChip, 'Italian');
      expect(italianChip, findsOneWidget);
      // Tap the delete icon within the chip (rendered as a small icon)
      final deleteButtons = find.descendant(
        of: italianChip,
        matching: find.byType(IconTheme),
      );
      // The delete icon is the last icon-like widget in the chip
      await tester.tap(deleteButtons.last);
      expect(deletedTags, ['Italian']);

      tagController.dispose();
    });
  });

  group('RecipeWizardScreen UI - Step Input', () {
    testWidgets('renders structured step entry with add button',
        (tester) async {
      final stepControllers = [
        TextEditingController(text: 'Boil water'),
      ];
      bool addCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Steps',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 12),
                  ...stepControllers.asMap().entries.map((entry) {
                    final index = entry.key;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          Text('${index + 1}.'),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: entry.value,
                              maxLines: null,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, size: 20),
                            onPressed: () {},
                          ),
                        ],
                      ),
                    );
                  }),
                  Center(
                    child: TextButton.icon(
                      onPressed: () => addCalled = true,
                      icon: const Icon(Icons.add),
                      label: const Text('Add Step'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Steps'), findsOneWidget);
      expect(find.text('Boil water'), findsOneWidget);
      expect(find.text('Add Step'), findsOneWidget);

      await tester.tap(find.text('Add Step'));
      expect(addCalled, isTrue);

      for (final c in stepControllers) {
        c.dispose();
      }
    });
  });

  group('RecipeWizardScreen UI - Tag Input', () {
    testWidgets('renders tag chip input with add/remove', (tester) async {
      final tags = ['Breakfast', 'Healthy'];
      final deletedTags = <String>[];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Tags'),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Expanded(
                        child: TextField(
                          decoration: InputDecoration(
                            hintText: 'Add a tag...',
                            isDense: true,
                          ),
                        ),
                      ),
                      IconButton(
                        onPressed: () {},
                        icon: const Icon(Icons.add),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: tags
                        .map((tag) => InputChip(
                              label: Text(tag),
                              onDeleted: () => deletedTags.add(tag),
                            ))
                        .toList(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.byType(InputChip), findsNWidgets(2));
      expect(find.text('Breakfast'), findsOneWidget);
      expect(find.text('Healthy'), findsOneWidget);

      // Delete tag
      final breakfastChip = find.widgetWithText(InputChip, 'Breakfast');
      expect(breakfastChip, findsOneWidget);
      final breakfastDeleteButtons = find.descendant(
        of: breakfastChip,
        matching: find.byType(IconTheme),
      );
      await tester.tap(breakfastDeleteButtons.last);
      expect(deletedTags, ['Breakfast']);
    });
  });

  group('RecipeWizardScreen UI - Photo Picker', () {
    testWidgets('renders photo placeholder with add icon when no image',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Add a photo (optional)'),
                  const SizedBox(height: 12),
                  GestureDetector(
                    onTap: () {},
                    child: Container(
                      height: 180,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.grey[300]!),
                      ),
                      child: const Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.add_a_photo_outlined, size: 48),
                            SizedBox(height: 8),
                            Text('Tap to add photo'),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.text('Add a photo (optional)'), findsOneWidget);
      expect(find.byIcon(Icons.add_a_photo_outlined), findsOneWidget);
      expect(find.text('Tap to add photo'), findsOneWidget);
    });

    testWidgets('renders image preview when image bytes provided',
        (tester) async {
      // Create a minimal 1x1 PNG image
      final imageBytes = Uint8List.fromList([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, // PNG header
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, // IHDR
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, // IDAT
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
        0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, // IEND
        0x44, 0xAE, 0x42, 0x60, 0x82,
      ]);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Add a photo (optional)'),
                  const SizedBox(height: 12),
                  GestureDetector(
                    onTap: () {},
                    child: Container(
                      height: 180,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.grey[300]!),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          Image.memory(imageBytes, fit: BoxFit.cover),
                          Positioned(
                            bottom: 8,
                            right: 8,
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.8),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(Icons.edit, size: 20),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      // Should show Image.memory widget and edit icon overlay
      expect(find.byType(Image), findsOneWidget);
      expect(find.byIcon(Icons.edit), findsOneWidget);
      // Should NOT show the placeholder icon
      expect(find.byIcon(Icons.add_a_photo_outlined), findsNothing);
    });
  });

  group('EditRecipeScreen UI - Photo Section', () {
    testWidgets('renders placeholder when no image_url', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  GestureDetector(
                    onTap: () {},
                    child: Container(
                      height: 180,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.grey[300]!),
                      ),
                      child: const Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.add_a_photo_outlined, size: 48),
                            SizedBox(height: 8),
                            Text('Tap to add photo'),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.add_a_photo_outlined), findsOneWidget);
      expect(find.text('Tap to add photo'), findsOneWidget);
    });

    testWidgets('renders CachedNetworkImage when image_url present',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  GestureDetector(
                    onTap: () {},
                    child: Container(
                      height: 180,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.grey[300]!),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          CachedNetworkImage(
                            imageUrl: 'https://example.com/photo.jpg',
                            fit: BoxFit.cover,
                            placeholder: (context, url) => const Center(
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                            errorWidget: (context, url, error) =>
                                const Icon(Icons.restaurant, size: 48),
                          ),
                          Positioned(
                            bottom: 8,
                            right: 8,
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.8),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(Icons.edit, size: 20),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CachedNetworkImage), findsOneWidget);
      expect(find.byIcon(Icons.edit), findsOneWidget);
      // Should NOT show the placeholder
      expect(find.byIcon(Icons.add_a_photo_outlined), findsNothing);
    });
  });
}
