import 'package:flutter/material.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';

import 'package:cissp_compass/design/legal_footer.dart';

/// Minimal placeholder used for routes not yet fully built.
class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        Text(l10n?.commonLoading ?? '…'),
        const LegalFooter(),
      ],
    );
  }
}
