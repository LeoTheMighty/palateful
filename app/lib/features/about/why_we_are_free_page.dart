import 'package:flutter/material.dart';

/// Static "Why we're free" page — Settings → About → Why we're free.
///
/// Body copy is the source-of-truth from
/// `_bmad-output/implementation-artifacts/pos-1-content-copy-for-all-surfaces.md`.
/// Renders a Palateful-vs-one-competitor toggle (NOT a 4-column grid)
/// per epic-recime-positioning party-mode refinement — 4 columns are
/// unreadable on a 360-px Android screen.
class WhyWeAreFreePage extends StatelessWidget {
  const WhyWeAreFreePage({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: _competitors.length,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Why we\'re free'),
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'vs Recime'),
              Tab(text: 'vs Recipe Notes'),
              Tab(text: 'vs Mela'),
            ],
          ),
        ),
        body: TabBarView(
          children: _competitors
              .map((c) => _CompetitorTab(competitor: c))
              .toList(),
        ),
      ),
    );
  }
}

class _CompetitorTab extends StatelessWidget {
  const _CompetitorTab({required this.competitor});

  final _Competitor competitor;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _IntroBody(),
          const SizedBox(height: 16),
          const Divider(height: 1),
          const SizedBox(height: 16),
          Row(
            children: [
              const Expanded(
                child: _HeaderCell(label: 'Palateful', isUs: true),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _HeaderCell(label: competitor.name, isUs: false),
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (final row in _rows) ...[
            _ComparisonRow(
              label: row.label,
              ours: row.palateful,
              theirs: competitor.values[row.key] ?? '—',
            ),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class _IntroBody extends StatelessWidget {
  const _IntroBody();

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Most recipe apps charge a subscription. Palateful doesn\'t, '
          'and that\'s a deliberate choice — not a marketing trick.',
          style: textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        Text(
          'Palateful is founder-funded. There\'s no investor in the room '
          'asking how we\'ll monetize you, no quarterly target that turns '
          '"import a recipe" into a feature behind a paywall. The cheapest '
          'way to keep your kitchen data yours is to never build the '
          'machinery that holds it hostage.',
          style: textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        Text(
          'We don\'t sell your data. We don\'t run ads. We don\'t have a '
          'premium tier sitting behind a coming-soon door. If we ever need '
          'money to keep the lights on, the answer will be donations or '
          'one-time payments — never a paywall on the recipes you\'ve '
          'already imported.',
          style: textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        Text(
          'This commitment is locked into the codebase: a CI check fails '
          'any pull request that introduces words like "premium," '
          '"subscription," or "upgrade." Free forever — and the build '
          'proves it.',
          style: textTheme.bodyMedium,
        ),
      ],
    );
  }
}

class _HeaderCell extends StatelessWidget {
  const _HeaderCell({required this.label, required this.isUs});

  final String label;
  final bool isUs;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: isUs
            ? colorScheme.primaryContainer
            : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w600,
          color: isUs ? colorScheme.onPrimaryContainer : null,
        ),
        textAlign: TextAlign.center,
      ),
    );
  }
}

class _ComparisonRow extends StatelessWidget {
  const _ComparisonRow({
    required this.label,
    required this.ours,
    required this.theirs,
  });

  final String label;
  final String ours;
  final String theirs;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: textTheme.labelMedium?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 6),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                ours,
                style: textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                theirs,
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Competitor {
  const _Competitor({required this.name, required this.values});
  final String name;
  final Map<String, String> values;
}

class _Row {
  const _Row({
    required this.key,
    required this.label,
    required this.palateful,
  });
  final String key;
  final String label;
  final String palateful;
}

const List<_Row> _rows = [
  _Row(key: 'price', label: 'Price', palateful: 'Free forever'),
  _Row(
    key: 'imports',
    label: 'Import sources',
    palateful: 'URL · photo · share-sheet · social',
  ),
  _Row(
    key: 'household',
    label: 'Household sharing',
    palateful: 'Real household, unlimited members',
  ),
  _Row(
    key: 'pantry',
    label: 'Pantry tracking',
    palateful: 'Yes — cooks decrement pantry',
  ),
  _Row(
    key: 'meals',
    label: 'Meal planning',
    palateful: 'Yes — Meals view + calendar',
  ),
  _Row(
    key: 'shopping',
    label: 'Shopping intelligence',
    palateful: 'Pantry-aware, household-shared',
  ),
  _Row(key: 'ads', label: 'Ads', palateful: 'None — ever'),
];

const List<_Competitor> _competitors = [
  _Competitor(
    name: 'Recime',
    values: {
      'price': '\$39.99–\$59.99/yr',
      'imports': 'URL · photo · social — 5/wk cap on free',
      'household': 'Single account; recipes public on free',
      'pantry': 'Not offered',
      'meals': 'Yes (paid)',
      'shopping': 'Basic list (paid)',
      'ads': 'None',
    },
  ),
  _Competitor(
    name: 'Recipe Notes',
    values: {
      'price': 'Free',
      'imports': 'URL · photo · share-sheet',
      'household': 'Single-user (export only)',
      'pantry': 'Not offered',
      'meals': 'Not offered',
      'shopping': 'Not offered',
      'ads': 'None',
    },
  ),
  _Competitor(
    name: 'Mela',
    values: {
      'price': '\$4.99 one-time (iOS)',
      'imports': 'URL · share-sheet · photo (paid)',
      'household': 'iCloud sync (single Apple ID)',
      'pantry': 'Not offered',
      'meals': 'Calendar view only',
      'shopping': 'Basic list, no household',
      'ads': 'None',
    },
  ),
];
