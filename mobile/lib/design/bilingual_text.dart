import 'package:cissp_api/cissp_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import 'package:cissp_compass/design/theme.dart';

/// Renders [Localized] content by question-content [mode] (`en`/`zh`/`bilingual`).
class BilingualText extends StatelessWidget {
  const BilingualText({
    super.key,
    required this.text,
    required this.mode,
    this.style,
    this.mutedStyle,
    this.markdown = false,
  });

  final Localized text;
  final String mode;
  final TextStyle? style;
  final TextStyle? mutedStyle;
  final bool markdown;

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
        if (showEn) _line(en ?? zh ?? '', base),
        if (showZh) ...[
          if (showEn) const SizedBox(height: 4),
          _line(zh ?? en ?? '', mode == 'bilingual' ? muted : base),
        ],
      ],
    );
  }

  Widget _line(String value, TextStyle? style) {
    if (!markdown) return Text(value, style: style);
    return MarkdownBody(
      data: value,
      styleSheet: MarkdownStyleSheet(
        p: style,
        pPadding: EdgeInsets.zero,
        code: style?.copyWith(
          fontFamily: 'monospace',
          backgroundColor: AppColors.canvas,
        ),
      ),
      softLineBreak: true,
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

bool localizedHasContent(Localized loc) {
  return (loc.en != null && loc.en!.trim().isNotEmpty) ||
      (loc.zh != null && loc.zh!.trim().isNotEmpty);
}

/// Post-submit / exam-review explanation block (rationale, key points, per-option).
class ExplanationPanel extends StatelessWidget {
  const ExplanationPanel({
    super.key,
    required this.mode,
    required this.rationale,
    required this.keyPoints,
    required this.perOption,
    required this.keyPointsLabel,
    required this.optionExplanationsLabel,
  });

  final String mode;
  final Localized rationale;
  final Localized keyPoints;
  final List<PerOptionExplanation> perOption;
  final String keyPointsLabel;
  final String optionExplanationsLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (localizedHasContent(rationale))
          BilingualText(text: rationale, mode: mode, markdown: true),
        if (localizedHasContent(keyPoints)) ...[
          const SizedBox(height: 12),
          Text(keyPointsLabel, style: theme.textTheme.labelLarge),
          const SizedBox(height: 4),
          BilingualText(text: keyPoints, mode: mode, markdown: true),
        ],
        if (perOption.any((p) => localizedHasContent(p.explanation))) ...[
          const SizedBox(height: 12),
          Text(optionExplanationsLabel, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          for (final p in perOption)
            if (localizedHasContent(p.explanation))
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${String.fromCharCode(65 + p.orderIndex)}. ',
                      style: theme.textTheme.labelLarge?.copyWith(
                        color: p.isCorrect
                            ? AppColors.success
                            : AppColors.muted,
                      ),
                    ),
                    Expanded(
                      child: BilingualText(
                        text: p.explanation,
                        mode: mode,
                        markdown: true,
                      ),
                    ),
                  ],
                ),
              ),
        ],
      ],
    );
  }
}
