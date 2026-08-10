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

final _dashboardProvider = FutureProvider.autoDispose<_DashData>((ref) async {
  final api = ref.watch(cisspApiProvider);
  final dash = await api.dashboard();
  List<DomainMastery> domains = const [];
  try {
    domains = await api.domainMastery();
  } catch (_) {}
  ReviewRecommendation? rec;
  try {
    rec = await api.recommendation();
  } catch (_) {}
  return _DashData(dash: dash, domains: domains, rec: rec);
});

class _DashData {
  const _DashData({
    required this.dash,
    required this.domains,
    this.rec,
  });
  final DashboardOut dash;
  final List<DomainMastery> domains;
  final ReviewRecommendation? rec;
}

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final async = ref.watch(_dashboardProvider);

    return async.when(
      loading: () => Center(child: Text(l10n.dashboardLoading)),
      error: (_, __) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(l10n.dashboardLoadFailed),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => ref.invalidate(_dashboardProvider),
              child: Text(l10n.commonRetry),
            ),
          ],
        ),
      ),
      data: (data) {
        final d = data.dash;
        final empty = d.totalAnswered == 0;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              l10n.dashboardEyebrow.toUpperCase(),
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.muted,
                    letterSpacing: 1.2,
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              l10n.dashboardTitle,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              l10n.dashboardDescription,
              style: TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 20),
            if (empty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.dashboardNoActivity,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(l10n.dashboardNoActivityDesc),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: () => context.go('/practice'),
                        child: Text(l10n.dashboardStartPracticing),
                      ),
                    ],
                  ),
                ),
              )
            else ...[
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  _StatChip(
                    label: l10n.dashboardAccuracy,
                    value: fmtPct(d.accuracy),
                  ),
                  _StatChip(
                    label: l10n.dashboardAnswered,
                    value: '${d.totalAnswered}',
                  ),
                  _StatChip(
                    label: l10n.dashboardStudyTime,
                    value: fmtDuration(d.studyTimeMs),
                  ),
                  _StatChip(
                    label: l10n.dashboardStreak,
                    value: l10n.dashboardStreakDays(d.streakDays),
                  ),
                ],
              ),
              if (data.domains.isNotEmpty) ...[
                const SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        l10n.dashboardDomainMastery,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                    ),
                    TextButton(
                      onPressed: () => context.go('/analytics'),
                      child: Text(l10n.analyticsTitle),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Center(
                  child: DomainCompass(
                    segments: [
                      for (final m in data.domains)
                        CompassSegment(number: m.number, accuracy: m.accuracy),
                    ],
                  ),
                ),
              ],
            ],
            const SizedBox(height: 24),
            _ActionCard(
              title: l10n.dashboardPracticeTitle,
              body: l10n.dashboardPracticeDesc,
              cta: l10n.dashboardStartPracticing,
              onTap: () => context.go('/practice'),
            ),
            const SizedBox(height: 12),
            _ActionCard(
              title: l10n.dashboardMockExamTitle,
              body: l10n.dashboardMockExamDesc,
              cta: l10n.dashboardStartExamCta,
              onTap: () => context.go('/exam'),
            ),
            const SizedBox(height: 12),
            _ActionCard(
              title: l10n.dashboardReviewTitle,
              body: l10n.dashboardReviewDesc,
              cta: l10n.dashboardReviewCta,
              onTap: () => context.go('/review'),
            ),
            if (data.rec != null && data.rec!.rationale.isNotEmpty) ...[
              const SizedBox(height: 24),
              Text(
                l10n.dashboardTodayRec,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              const SizedBox(height: 8),
              Text(data.rec!.rationale),
            ],
            const LegalFooter(),
          ],
        );
      },
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 150,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              const SizedBox(height: 4),
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.title,
    required this.body,
    required this.cta,
    required this.onTap,
  });
  final String title;
  final String body;
  final String cta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(body, style: const TextStyle(color: AppColors.muted)),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(onPressed: onTap, child: Text(cta)),
            ),
          ],
        ),
      ),
    );
  }
}
