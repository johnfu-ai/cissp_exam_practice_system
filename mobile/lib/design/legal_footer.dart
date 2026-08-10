import 'package:flutter/material.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';

import 'package:cissp_compass/design/theme.dart';

/// Trademark + independent-study disclaimer (NFR-COMP-03/04).
class LegalFooter extends StatelessWidget {
  const LegalFooter({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final style = Theme.of(context).textTheme.bodySmall?.copyWith(
          color: AppColors.muted,
          height: 1.35,
        );
    return Semantics(
      container: true,
      explicitChildNodes: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
        child: Column(
          children: [
            Text(l10n.legalTrademark, textAlign: TextAlign.center, style: style),
            const SizedBox(height: 4),
            Text(l10n.legalNotOfficial, textAlign: TextAlign.center, style: style),
          ],
        ),
      ),
    );
  }
}
