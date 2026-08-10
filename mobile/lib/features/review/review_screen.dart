import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/core/session_tracker.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';

class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({super.key});

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  String? _busySubset;

  Future<void> _start(String subset) async {
    final l10n = AppLocalizations.of(context)!;
    setState(() => _busySubset = subset);
    try {
      final api = ref.read(cisspApiProvider);
      final session = await api.createPractice({
        'count': 25,
        'subset': subset,
        'order_mode': 'random',
      });
      final prefs = ref.read(prefsStoreProvider);
      final ids = await prefs.getPracticeSessionIds();
      await prefs.setPracticeSessionIds(trackSessionId(ids, session.id));
      if (mounted) context.go('/practice/sessions/${session.id}');
    } on DioException {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.reviewCouldNotStart)),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.reviewCouldNotStart)),
        );
      }
    } finally {
      if (mounted) setState(() => _busySubset = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.reviewTitle, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(l10n.reviewDescription),
        const SizedBox(height: 16),
        _ReviewCard(
          icon: Icons.error_outline,
          title: l10n.reviewWrong,
          description: l10n.reviewWrongDesc,
          busy: _busySubset == 'wrong',
          onStart: () => _start('wrong'),
          cta: l10n.reviewStart,
        ),
        _ReviewCard(
          icon: Icons.bookmark_border,
          title: l10n.reviewBookmarked,
          description: l10n.reviewBookmarkedDesc,
          busy: _busySubset == 'bookmarked',
          onStart: () => _start('bookmarked'),
          cta: l10n.reviewStart,
        ),
        _ReviewCard(
          icon: Icons.flag_outlined,
          title: l10n.reviewFlagged,
          description: l10n.reviewFlaggedDesc,
          busy: _busySubset == 'needs_review',
          onStart: () => _start('needs_review'),
          cta: l10n.reviewStart,
        ),
        const LegalFooter(),
      ],
    );
  }
}

class _ReviewCard extends StatelessWidget {
  const _ReviewCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.busy,
    required this.onStart,
    required this.cta,
  });

  final IconData icon;
  final String title;
  final String description;
  final bool busy;
  final VoidCallback onStart;
  final String cta;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: AppColors.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(description, style: TextStyle(color: AppColors.muted)),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: busy ? null : onStart,
              child: Text(busy ? '…' : cta),
            ),
          ],
        ),
      ),
    );
  }
}
