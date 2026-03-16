import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/theme/app_colors.dart';

class RecipeWizardScreen extends StatefulWidget {
  const RecipeWizardScreen({super.key});

  @override
  State<RecipeWizardScreen> createState() => _RecipeWizardScreenState();
}

class _RecipeWizardScreenState extends State<RecipeWizardScreen> {
  final _pageController = PageController();
  final _apiClient = getIt<ApiClient>();
  int _currentStep = 0;
  final _totalSteps = 4;
  bool _isSaving = false;

  // Form controllers
  final _nameController = TextEditingController();
  final _prepTimeController = TextEditingController();
  final _cookTimeController = TextEditingController();
  final _servingsController = TextEditingController();
  final _sourceUrlController = TextEditingController();

  // Form data
  String? _imageUrl;
  List<Map<String, dynamic>> _ingredients = [];
  List<Map<String, dynamic>> _steps = [];
  String? _mealType;
  List<String> _tags = [];
  String? _selectedRecipeBookId;
  List<dynamic> _recipeBooks = [];

  @override
  void initState() {
    super.initState();
    _loadRecipeBooks();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _prepTimeController.dispose();
    _cookTimeController.dispose();
    _servingsController.dispose();
    _sourceUrlController.dispose();
    _pageController.dispose();
    super.dispose();
  }

  Future<void> _loadRecipeBooks() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      setState(() {
        _recipeBooks = response.data['items'] ?? [];
        if (_recipeBooks.isNotEmpty) {
          _selectedRecipeBookId = _recipeBooks.first['id'];
        }
      });
    } catch (e) {
      // Ignore - user can still create recipe
    }
  }

  void _nextStep() {
    if (_currentStep < _totalSteps - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      _saveRecipe();
    }
  }

  void _previousStep() {
    if (_currentStep > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      context.pop();
    }
  }

  void _goToStep(int step) {
    _pageController.animateToPage(
      step,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  Future<void> _saveRecipe() async {
    if (_nameController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a recipe name')),
      );
      _goToStep(0);
      return;
    }

    if (_selectedRecipeBookId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please create a recipe book first')),
      );
      return;
    }

    setState(() => _isSaving = true);

    try {
      final structuredSteps = _steps.asMap().entries.map((e) => {
        'step_number': e.key + 1,
        'instruction': e.value['instruction'] ?? '',
      }).toList();

      final recipeData = {
        'name': _nameController.text,
        'prep_time': int.tryParse(_prepTimeController.text),
        'cook_time': int.tryParse(_cookTimeController.text),
        'servings': int.tryParse(_servingsController.text),
        'image_url': _imageUrl,
        'source_url': _sourceUrlController.text.isEmpty
            ? null
            : _sourceUrlController.text,
        'tags': _tags.isEmpty ? [] : _tags,
        'ingredients': _ingredients.isEmpty ? [] : _ingredients,
        'steps': structuredSteps.isEmpty ? [] : structuredSteps,
      };

      await _apiClient.createRecipe(_selectedRecipeBookId!, recipeData);

      if (mounted) {
        HapticFeedback.heavyImpact();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Recipe created successfully!'),
            backgroundColor: AppColors.success,
          ),
        );
        context.go('/');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to create recipe: $e')),
        );
        setState(() => _isSaving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.cream,
      appBar: AppBar(
        backgroundColor: AppColors.cream,
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
        title: const Text('New Recipe'),
        actions: [
          if (_currentStep < _totalSteps - 1)
            TextButton(
              onPressed: _nextStep,
              child: const Text('Skip'),
            ),
        ],
      ),
      body: Column(
        children: [
          // Progress indicator
          _buildProgressBar(),

          // Step content
          Expanded(
            child: PageView(
              controller: _pageController,
              onPageChanged: (index) {
                setState(() => _currentStep = index);
              },
              children: [
                _StepName(
                  nameController: _nameController,
                  imageUrl: _imageUrl,
                  onImageChanged: (v) => setState(() => _imageUrl = v),
                ),
                _StepIngredients(
                  ingredients: _ingredients,
                  onChanged: (v) => setState(() => _ingredients = v),
                ),
                _StepSteps(
                  steps: _steps,
                  onChanged: (v) => setState(() => _steps = v),
                ),
                _StepDetails(
                  prepTimeController: _prepTimeController,
                  cookTimeController: _cookTimeController,
                  servingsController: _servingsController,
                  sourceUrlController: _sourceUrlController,
                  mealType: _mealType,
                  tags: _tags,
                  selectedRecipeBookId: _selectedRecipeBookId,
                  recipeBooks: _recipeBooks,
                  onMealTypeChanged: (v) => setState(() => _mealType = v),
                  onTagsChanged: (v) => setState(() => _tags = v),
                  onRecipeBookChanged: (v) =>
                      setState(() => _selectedRecipeBookId = v),
                ),
              ],
            ),
          ),

          // Navigation buttons
          _buildNavigation(),
        ],
      ),
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Step dots
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(_totalSteps, (index) {
              final isActive = index == _currentStep;
              final isCompleted = index < _currentStep;

              return GestureDetector(
                onTap: () => _goToStep(index),
                child: Container(
                  width: isActive ? 24 : 10,
                  height: 10,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: isActive || isCompleted
                        ? AppColors.chocolate
                        : AppColors.beigeAccent,
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 8),

          // Step label
          Text(
            ['Name & Photo', 'Ingredients', 'Instructions', 'Details']
                [_currentStep],
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavigation() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // Back button
            if (_currentStep > 0)
              OutlinedButton(
                onPressed: _previousStep,
                child: const Icon(Icons.arrow_back),
              )
            else
              const SizedBox(width: 48),

            const Spacer(),

            // Next/Save button
            ElevatedButton(
              onPressed: _isSaving ? null : _nextStep,
              child: _isSaving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.cream,
                      ),
                    )
                  : Text(
                      _currentStep == _totalSteps - 1 ? 'Save Recipe' : 'Next',
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// Step 1: Name & Photo
class _StepName extends StatelessWidget {
  final TextEditingController nameController;
  final String? imageUrl;
  final ValueChanged<String?> onImageChanged;

  const _StepName({
    required this.nameController,
    required this.imageUrl,
    required this.onImageChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'What are you cooking?',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Give your recipe a name',
            style: TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),

          // Name input
          TextField(
            controller: nameController,
            decoration: const InputDecoration(
              labelText: 'Recipe Name',
              hintText: 'e.g., Grandma\'s Chicken Soup',
            ),
            textCapitalization: TextCapitalization.words,
            autofocus: true,
          ),
          const SizedBox(height: 32),

          // Photo placeholder
          const Text(
            'Add a photo (optional)',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w500,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () {
              // TODO: Implement image picker
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Photo picker coming soon!')),
              );
            },
            child: Container(
              height: 180,
              decoration: BoxDecoration(
                color: AppColors.beige,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: AppColors.beigeAccent,
                  style: BorderStyle.solid,
                ),
              ),
              child: const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.add_a_photo_outlined,
                      size: 48,
                      color: AppColors.hazelnut,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Tap to add photo',
                      style: TextStyle(color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Step 2: Ingredients
class _StepIngredients extends StatefulWidget {
  final List<Map<String, dynamic>> ingredients;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const _StepIngredients({
    required this.ingredients,
    required this.onChanged,
  });

  @override
  State<_StepIngredients> createState() => _StepIngredientsState();
}

class _StepIngredientsState extends State<_StepIngredients> {
  final _ingredientController = TextEditingController();

  void _addIngredient() {
    final text = _ingredientController.text.trim();
    if (text.isEmpty) return;

    // Simple parsing: "2 cups flour" -> quantity, unit, name
    final parts = text.split(' ');
    String? quantity;
    String? unit;
    String name;

    if (parts.length >= 3 &&
        double.tryParse(parts[0].replaceAll(RegExp(r'[^\d.]'), '')) != null) {
      quantity = parts[0];
      unit = parts[1];
      name = parts.sublist(2).join(' ');
    } else if (parts.length >= 2 &&
        double.tryParse(parts[0].replaceAll(RegExp(r'[^\d.]'), '')) != null) {
      quantity = parts[0];
      name = parts.sublist(1).join(' ');
    } else {
      name = text;
    }

    final newIngredient = {
      'quantity_display': quantity ?? '',
      'unit_display': unit ?? '',
      'ingredient': {'canonical_name': name},
    };

    final updated = [...widget.ingredients, newIngredient];
    widget.onChanged(updated);
    _ingredientController.clear();
  }

  void _removeIngredient(int index) {
    final updated = List<Map<String, dynamic>>.from(widget.ingredients);
    updated.removeAt(index);
    widget.onChanged(updated);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Add ingredients',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Type ingredient with amount (e.g., "2 cups flour")',
            style: TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),

          // Input row
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _ingredientController,
                  decoration: const InputDecoration(
                    hintText: '2 cups all-purpose flour',
                  ),
                  textCapitalization: TextCapitalization.sentences,
                  onSubmitted: (_) => _addIngredient(),
                ),
              ),
              const SizedBox(width: 12),
              IconButton.filled(
                onPressed: _addIngredient,
                icon: const Icon(Icons.add),
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.chocolate,
                  foregroundColor: AppColors.cream,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Ingredients list
          Expanded(
            child: widget.ingredients.isEmpty
                ? const Center(
                    child: Text(
                      'No ingredients added yet',
                      style: TextStyle(color: AppColors.textTertiary),
                    ),
                  )
                : ListView.builder(
                    itemCount: widget.ingredients.length,
                    itemBuilder: (context, index) {
                      final ing = widget.ingredients[index];
                      final quantity = ing['quantity_display'] ?? '';
                      final unit = ing['unit_display'] ?? '';
                      final name =
                          ing['ingredient']?['canonical_name'] ?? 'Unknown';

                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Container(
                          width: 40,
                          height: 40,
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
                        title: Text('$quantity $unit $name'.trim()),
                        trailing: IconButton(
                          icon: const Icon(Icons.close, size: 20),
                          onPressed: () => _removeIngredient(index),
                          color: AppColors.textTertiary,
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

// Step 3: Structured Steps
class _StepSteps extends StatefulWidget {
  final List<Map<String, dynamic>> steps;
  final ValueChanged<List<Map<String, dynamic>>> onChanged;

  const _StepSteps({
    required this.steps,
    required this.onChanged,
  });

  @override
  State<_StepSteps> createState() => _StepStepsState();
}

class _StepStepsState extends State<_StepSteps> {
  final _controllers = <TextEditingController>[];

  @override
  void initState() {
    super.initState();
    _syncControllers();
  }

  @override
  void didUpdateWidget(covariant _StepSteps oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.steps.length != widget.steps.length) {
      _syncControllers();
    }
  }

  void _syncControllers() {
    // Dispose extra controllers
    while (_controllers.length > widget.steps.length) {
      _controllers.removeLast().dispose();
    }
    // Add missing controllers
    while (_controllers.length < widget.steps.length) {
      final idx = _controllers.length;
      _controllers.add(TextEditingController(
        text: widget.steps[idx]['instruction'] ?? '',
      ));
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  void _addStep() {
    final updated = [...widget.steps, {'instruction': ''}];
    widget.onChanged(updated);
  }

  void _removeStep(int index) {
    _controllers[index].dispose();
    _controllers.removeAt(index);
    final updated = List<Map<String, dynamic>>.from(widget.steps);
    updated.removeAt(index);
    widget.onChanged(updated);
  }

  void _onStepTextChanged(int index, String text) {
    final updated = List<Map<String, dynamic>>.from(widget.steps);
    updated[index] = {...updated[index], 'instruction': text};
    widget.onChanged(updated);
  }

  void _onReorder(int oldIndex, int newIndex) {
    if (newIndex > oldIndex) newIndex--;
    final updated = List<Map<String, dynamic>>.from(widget.steps);
    final item = updated.removeAt(oldIndex);
    updated.insert(newIndex, item);
    final ctrl = _controllers.removeAt(oldIndex);
    _controllers.insert(newIndex, ctrl);
    widget.onChanged(updated);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'How do you make it?',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Add each step individually — drag to reorder',
            style: TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),

          // Steps list
          Expanded(
            child: widget.steps.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          'No steps added yet',
                          style: TextStyle(color: AppColors.textTertiary),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _addStep,
                          icon: const Icon(Icons.add),
                          label: const Text('Add First Step'),
                        ),
                      ],
                    ),
                  )
                : ReorderableListView.builder(
                    itemCount: widget.steps.length,
                    onReorder: _onReorder,
                    itemBuilder: (context, index) {
                      return Padding(
                        key: ValueKey('step_$index'),
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Drag handle + step number
                            ReorderableDragStartListener(
                              index: index,
                              child: Container(
                                width: 36,
                                height: 36,
                                margin: const EdgeInsets.only(top: 8),
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
                            ),
                            const SizedBox(width: 12),
                            // Instruction field
                            Expanded(
                              child: TextField(
                                controller: _controllers[index],
                                onChanged: (v) => _onStepTextChanged(index, v),
                                decoration: InputDecoration(
                                  hintText: 'Step ${index + 1} instruction...',
                                ),
                                maxLines: null,
                                textCapitalization:
                                    TextCapitalization.sentences,
                              ),
                            ),
                            // Remove button
                            IconButton(
                              icon: const Icon(Icons.close, size: 20),
                              onPressed: () => _removeStep(index),
                              color: AppColors.textTertiary,
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),

          // Add step button
          if (widget.steps.isNotEmpty)
            Center(
              child: TextButton.icon(
                onPressed: _addStep,
                icon: const Icon(Icons.add),
                label: const Text('Add Step'),
              ),
            ),
        ],
      ),
    );
  }
}

// Step 4: Details
class _StepDetails extends StatefulWidget {
  final TextEditingController prepTimeController;
  final TextEditingController cookTimeController;
  final TextEditingController servingsController;
  final TextEditingController sourceUrlController;
  final String? mealType;
  final List<String> tags;
  final String? selectedRecipeBookId;
  final List<dynamic> recipeBooks;
  final ValueChanged<String?> onMealTypeChanged;
  final ValueChanged<List<String>> onTagsChanged;
  final ValueChanged<String?> onRecipeBookChanged;

  const _StepDetails({
    required this.prepTimeController,
    required this.cookTimeController,
    required this.servingsController,
    required this.sourceUrlController,
    required this.mealType,
    required this.tags,
    required this.selectedRecipeBookId,
    required this.recipeBooks,
    required this.onMealTypeChanged,
    required this.onTagsChanged,
    required this.onRecipeBookChanged,
  });

  @override
  State<_StepDetails> createState() => _StepDetailsState();
}

class _StepDetailsState extends State<_StepDetails> {
  final _tagController = TextEditingController();

  @override
  void dispose() {
    _tagController.dispose();
    super.dispose();
  }

  void _addTag() {
    final text = _tagController.text.trim();
    if (text.isEmpty || widget.tags.contains(text)) return;
    widget.onTagsChanged([...widget.tags, text]);
    _tagController.clear();
  }

  void _removeTag(String tag) {
    widget.onTagsChanged(widget.tags.where((t) => t != tag).toList());
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Final details',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 24),

          // Recipe Book selector
          if (widget.recipeBooks.isNotEmpty) ...[
            const Text(
              'Save to Recipe Book',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: widget.selectedRecipeBookId,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.book_outlined),
              ),
              items: widget.recipeBooks.map((book) {
                return DropdownMenuItem(
                  value: book['id'] as String,
                  child: Text(book['name'] ?? 'Untitled'),
                );
              }).toList(),
              onChanged: widget.onRecipeBookChanged,
            ),
            const SizedBox(height: 24),
          ],

          // Time inputs
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: widget.prepTimeController,
                  decoration: const InputDecoration(
                    labelText: 'Prep time',
                    suffixText: 'min',
                  ),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: TextField(
                  controller: widget.cookTimeController,
                  decoration: const InputDecoration(
                    labelText: 'Cook time',
                    suffixText: 'min',
                  ),
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Servings
          TextField(
            controller: widget.servingsController,
            decoration: const InputDecoration(
              labelText: 'Servings',
              hintText: 'e.g., 4',
            ),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 24),

          // Source URL
          TextField(
            controller: widget.sourceUrlController,
            decoration: const InputDecoration(
              labelText: 'Source URL (optional)',
              hintText: 'https://example.com/recipe',
              prefixIcon: Icon(Icons.link),
            ),
            keyboardType: TextInputType.url,
          ),
          const SizedBox(height: 24),

          // Tags
          const Text(
            'Tags',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _tagController,
                  decoration: const InputDecoration(
                    hintText: 'Add a tag...',
                    isDense: true,
                  ),
                  onSubmitted: (_) => _addTag(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: _addTag,
                icon: const Icon(Icons.add),
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.chocolate,
                  foregroundColor: AppColors.cream,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (widget.tags.isNotEmpty)
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: widget.tags
                  .map((tag) => InputChip(
                        label: Text(tag),
                        onDeleted: () => _removeTag(tag),
                        backgroundColor: AppColors.beige,
                      ))
                  .toList(),
            ),
          const SizedBox(height: 24),

          // Meal type
          const Text(
            'Meal Type',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _MealChip(
                icon: Icons.free_breakfast,
                label: 'Breakfast',
                value: 'breakfast',
                isSelected: widget.mealType == 'breakfast',
                onTap: () => widget.onMealTypeChanged(
                    widget.mealType == 'breakfast' ? null : 'breakfast'),
              ),
              _MealChip(
                icon: Icons.lunch_dining,
                label: 'Lunch',
                value: 'lunch',
                isSelected: widget.mealType == 'lunch',
                onTap: () => widget.onMealTypeChanged(
                    widget.mealType == 'lunch' ? null : 'lunch'),
              ),
              _MealChip(
                icon: Icons.dinner_dining,
                label: 'Dinner',
                value: 'dinner',
                isSelected: widget.mealType == 'dinner',
                onTap: () => widget.onMealTypeChanged(
                    widget.mealType == 'dinner' ? null : 'dinner'),
              ),
              _MealChip(
                icon: Icons.cake,
                label: 'Dessert',
                value: 'dessert',
                isSelected: widget.mealType == 'dessert',
                onTap: () => widget.onMealTypeChanged(
                    widget.mealType == 'dessert' ? null : 'dessert'),
              ),
              _MealChip(
                icon: Icons.cookie,
                label: 'Snack',
                value: 'snack',
                isSelected: widget.mealType == 'snack',
                onTap: () => widget.onMealTypeChanged(
                    widget.mealType == 'snack' ? null : 'snack'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MealChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final bool isSelected;
  final VoidCallback onTap;

  const _MealChip({
    required this.icon,
    required this.label,
    required this.value,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = isSelected ? AppColors.cream : AppColors.textPrimary;
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.chocolate : AppColors.beige,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
