import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/compass.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';
import 'package:cissp_compass/features/exam/format.dart';

final _domainsProvider = FutureProvider.autoDispose((ref) {
  return ref.watch(cisspApiProvider).domainMastery();
});

class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final async = ref.watch(_domainsProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.analyticsTitle,
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(l10n.analyticsDescription,
            style: const TextStyle(color: AppColors.muted)),
        const SizedBox(height: 16),
        async.when(
          loading: () => Text(l10n.analyticsLoading),
          error: (_, __) => Column(
            children: [
              Text(l10n.analyticsLoadFailed),
              TextButton(
                onPressed: () => ref.invalidate(_domainsProvider),
                child: Text(l10n.commonRetry),
              ),
            ],
          ),
          data: (domains) {
            if (domains.isEmpty) {
              return Text(l10n.dashboardNoActivity);
            }
            return Column(
              children: [
                DomainCompass(
                  segments: [
                    for (final m in domains)
                      CompassSegment(number: m.number, accuracy: m.accuracy),
                  ],
                ),
                const SizedBox(height: 16),
                for (final m in domains)
                  ListTile(
                    title: Text('${m.number}. ${m.name}'),
                    subtitle: Text(
                      '${l10n.analyticsColAnswered}: ${m.answered}',
                    ),
                    trailing: Text(
                      m.answered == 0 ? '—' : fmtPct(m.accuracy),
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
              ],
            );
          },
        ),
        TextButton(
          onPressed: () => context.go('/dashboard'),
          child: Text(l10n.navHome),
        ),
        const LegalFooter(),
      ],
    );
  }
}
