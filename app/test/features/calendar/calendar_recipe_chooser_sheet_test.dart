import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palateful/features/calendar/widgets/calendar_recipe_chooser_sheet.dart';
import 'package:palateful/features/meals/models/meal.dart';

MealComponent _c(String recipeId, String name,
        {bool available = true, int order = 0, String? book}) =>
    MealComponent(
      recipeId: recipeId,
      name: name,
      orderIndex: order,
      available: available,
      bookName: book,
    );

Widget _router(String? Function()? recipeIdTap, List<MealComponent> comps,
    {String mealName = 'Kale Salad Meal'}) {
  final router = GoRouter(
    initialLocation: '/start',
    routes: [
      GoRoute(
        path: '/start',
        builder: (ctx, _) => Scaffold(
          body: Builder(
            builder: (builderCtx) => Center(
              child: TextButton(
                onPressed: () => showModalBottomSheet<void>(
                  context: builderCtx,
                  isScrollControlled: true,
                  builder: (_) => CalendarRecipeChooserSheet(
                    components: comps,
                    mealName: mealName,
                  ),
                ),
                child: const Text('Open chooser'),
              ),
            ),
          ),
        ),
      ),
      GoRoute(
        path: '/recipes/:id',
        builder: (ctx, state) {
          recipeIdTap?.call();
          return Scaffold(
            appBar: AppBar(title: Text('Recipe ${state.pathParameters['id']}')),
          );
        },
      ),
    ],
  );
  return MaterialApp.router(routerConfig: router);
}

void main() {
  testWidgets('renders title "Which recipe?" + mealName subtitle',
      (tester) async {
    await tester.pumpWidget(_router(null, [
      _c('r1', 'Kale Salad'),
      _c('r2', 'Lemon Dressing', order: 1),
    ]));
    await tester.tap(find.text('Open chooser'));
    await tester.pumpAndSettle();

    expect(find.text('Which recipe?'), findsOneWidget);
    expect(find.text('Kale Salad Meal'), findsOneWidget);
    expect(find.text('Kale Salad'), findsOneWidget);
    expect(find.text('Lemon Dressing'), findsOneWidget);
  });

  testWidgets('omits unavailable components entirely', (tester) async {
    await tester.pumpWidget(_router(null, [
      _c('r1', 'Kale Salad'),
      _c('r2', 'Archived Dressing', available: false, order: 1),
      _c('r3', 'Lemon Wedge', order: 2),
    ]));
    await tester.tap(find.text('Open chooser'));
    await tester.pumpAndSettle();

    expect(find.text('Kale Salad'), findsOneWidget);
    expect(find.text('Lemon Wedge'), findsOneWidget);
    expect(find.text('Archived Dressing'), findsNothing);
  });

  testWidgets('tapping a row pushes /recipes/:id and pops chooser',
      (tester) async {
    var routed = false;
    await tester.pumpWidget(_router(() {
      routed = true;
      return null;
    }, [
      _c('r1', 'Kale Salad'),
      _c('r2', 'Lemon Dressing', order: 1),
    ]));
    await tester.tap(find.text('Open chooser'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Lemon Dressing'));
    await tester.pumpAndSettle();

    expect(routed, isTrue);
    expect(find.text('Recipe r2'), findsOneWidget);
    expect(find.byType(CalendarRecipeChooserSheet), findsNothing);
  });

  testWidgets('empty-available (all components archived) shows copy',
      (tester) async {
    await tester.pumpWidget(_router(null, [
      _c('r1', 'Archived A', available: false),
      _c('r2', 'Archived B', available: false, order: 1),
    ]));
    await tester.tap(find.text('Open chooser'));
    await tester.pumpAndSettle();

    expect(find.textContaining('No recipes are available'), findsOneWidget);
  });
}
