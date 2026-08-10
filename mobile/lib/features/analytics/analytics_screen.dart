import 'package:cissp_api/cissp_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/compass.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';
import 'package:cissp_compass/features/exam/format.dart';

class _AnalyticsBundle {
  const _AnalyticsBundle({
    required this.domains,
    required this.trend,
    required this.weakAreas,
    required this.errorTypes,
    required this.recommendation,
  });

  final List<DomainMastery> domains;
  final TrendOut? trend;
  final WeakAreasOut? weakAreas;
  final ErrorTypeOut? errorTypes;
  final ReviewRecommendation? recommendation;
}

final _analyticsProvider =
    FutureProvider.autoDispose.family<_AnalyticsBundle, int>((ref, window) async {
  final api = ref.watch(cisspApiProvider);
  final domains = await api.domainMastery();
  TrendOut? trend;
  WeakAreasOut? weak;
  ErrorTypeOut? errors;
  ReviewRecommendation? rec;
  try {
    trend = await api.trend(windowDays: window);
  } catch (_) {}
  try {
    weak = await api.weakAreas();
  } catch (_) {}
  try {
    errors = await api.errorTypes();
  } catch (_) {}
  try {
    rec = await api.recommendation();
  } catch (_) {}
  return _AnalyticsBundle(
    domains: domains,
    trend: trend,
    weakAreas: weak,
    errorTypes: errors,
    recommendation: rec,
  );
});

class AnalyticsScreen extends ConsumerStatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  ConsumerState<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends ConsumerState<AnalyticsScreen> {
  int _windowDays = 30;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final async = ref.watch(_analyticsProvider(_windowDays));

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.analyticsTitle,
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(l10n.analyticsDescription,
            style: const TextStyle(color: AppColors.muted)),
        const SizedBox(height: 12),
        SegmentedButton<int>(
          segments: const [
            ButtonSegment(value: 30, label: Text('30d')),
            ButtonSegment(value: 90, label: Text('90d')),
          ],
          selected: {_windowDays},
          onSelectionChanged: (s) => setState(() => _windowDays = s.first),
        ),
        const SizedBox(height: 16),
        async.when(
          loading: () => Text(l10n.analyticsLoading),
          error: (_, __) => Column(
            children: [
              Text(l10n.analyticsLoadFailed),
              TextButton(
                onPressed: () =>
                    ref.invalidate(_analyticsProvider(_windowDays)),
                child: Text(l10n.commonRetry),
              ),
            ],
          ),
          data: (bundle) {
            if (bundle.domains.isEmpty &&
                (bundle.trend?.points.isEmpty ?? true)) {
              return Text(l10n.dashboardNoActivity);
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.analyticsDomainMastery,
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                DomainCompass(
                  segments: [
                    for (final m in bundle.domains)
                      CompassSegment(number: m.number, accuracy: m.accuracy),
                  ],
                ),
                const SizedBox(height: 12),
                for (final m in bundle.domains)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('${m.number}. ${m.name}'),
                    subtitle: Text(
                      '${l10n.analyticsColAccuracy}: ${fmtPct(m.accuracy)} · '
                      '${l10n.analyticsColAnswered}: ${m.answered}',
                    ),
                  ),
                if (bundle.trend != null && bundle.trend!.points.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(l10n.analyticsAccuracyTrend,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  for (final p in bundle.trend!.points.take(14))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text(p.date),
                      trailing: Text(
                        '${fmtPct(p.accuracy)} (${p.correct}/${p.answered})',
                      ),
                    ),
                ],
                if (bundle.weakAreas != null) ...[
                  const SizedBox(height: 16),
                  Text(l10n.analyticsFocusAreas,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (bundle.weakAreas!.weakDomains.isEmpty &&
                      bundle.weakAreas!.weakKnowledgePoints.isEmpty)
                    Text(l10n.dashboardNoActivity,
                        style: const TextStyle(color: AppColors.muted)),
                  for (final w in bundle.weakAreas!.weakDomains)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(w.label),
                      subtitle: Text(
                        '${fmtPct(w.accuracy)} · ${w.correct}/${w.answered}',
                      ),
                    ),
                  if (bundle.weakAreas!.weakKnowledgePoints.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(l10n.analyticsWeakKp,
                        style: Theme.of(context).textTheme.titleSmall),
                    for (final w in bundle.weakAreas!.weakKnowledgePoints)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        title: Text(w.label),
                        trailing: Text(fmtPct(w.accuracy)),
                      ),
                  ],
                ],
                if (bundle.errorTypes != null &&
                    bundle.errorTypes!.distribution.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Text(l10n.analyticsErrorTypes,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  for (final e in bundle.errorTypes!.distribution)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text(e.errorType ?? '—'),
                      trailing: Text('${e.count}'),
                    ),
                ],
                if (bundle.recommendation != null) ...[
                  const SizedBox(height: 16),
                  Text(l10n.dashboardTodayRec,
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  if (bundle.recommendation!.focusDomain != null)
                    Text(
                      bundle.recommendation!.focusDomain!.label,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  if (bundle.recommendation!.rationale.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(bundle.recommendation!.rationale),
                  ],
                  if (bundle.recommendation!.wrongToReview.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      '${l10n.practiceWrongList}: ${bundle.recommendation!.wrongToReview.length}',
                    ),
                  ],
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: () => context.go('/review'),
                    child: Text(l10n.dashboardReviewCta),
                  ),
                ],
              ],
            );
          },
        ),
        const LegalFooter(),
      ],
    );
  }
}
