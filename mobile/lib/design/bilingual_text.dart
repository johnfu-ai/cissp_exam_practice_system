import 'package:cissp_api/cissp_api.dart';
import 'package:flutter/material.dart';

import 'package:cissp_compass/design/theme.dart';

/// Renders [Localized] content by question-content [mode] (`en`/`zh`/`bilingual`).
class BilingualText extends StatelessWidget {
  const BilingualText({
    super.key,
    required this.text,
    required this.mode,
    this.style,
    this.mutedStyle,
  });

  final Localized text;
  final String mode;
  final TextStyle? style;
  final TextStyle? mutedStyle;

  @override
  Widget build(BuildContext context) {
    final base = style ?? Theme.of(context).textTheme.bodyLarge;
    final muted = mutedStyle ??
        base?.copyWith(color: AppColors.muted) ??
        const TextStyle(color: AppColors.muted);

    final en = text.en;
    final zh = text.zh;
    final showEn = mode != 'zh' && (en ?? zh) != null;
    final showZh = mode != 'en' && (zh ?? en) != null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (showEn) Text(en ?? zh ?? '', style: base),
        if (showZh) ...[
          if (showEn) const SizedBox(height: 4),
          Text(zh ?? en ?? '', style: mode == 'bilingual' ? muted : base),
        ],
      ],
    );
  }
}

/// Flatten a [Localized] value for single-line contexts.
String localizedText(Localized loc, String mode) {
  if (mode == 'en') return loc.en ?? loc.zh ?? '';
  if (mode == 'zh') return loc.zh ?? loc.en ?? '';
  final parts = [loc.en, loc.zh].whereType<String>().where((s) => s.isNotEmpty);
  return parts.join('  /  ');
}
