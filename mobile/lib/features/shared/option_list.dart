import 'package:cissp_api/cissp_api.dart';
import 'package:flutter/material.dart';

import 'package:cissp_compass/design/bilingual_text.dart';
import 'package:cissp_compass/design/theme.dart';

/// Renders options in [displayOrder] (canonical [order_index] values).
///
/// Selection callbacks always receive the option's canonical `order_index`,
/// never the display slot index. When [result] is set, rows are colored for
/// correct / incorrect feedback.
class OptionList extends StatelessWidget {
  const OptionList({
    super.key,
    required this.options,
    required this.selectedIndexes,
    required this.questionType,
    required this.languageMode,
    required this.onToggle,
    this.result,
    this.displayOrder,
    this.enabled = true,
  });

  final List<OptionDelivery> options;
  final List<int> selectedIndexes;
  final String questionType;
  final String languageMode;
  final void Function(int orderIndex) onToggle;
  final AnswerResult? result;

  /// Display order as canonical `order_index` values. Defaults to natural order.
  final List<int>? displayOrder;
  final bool enabled;

  bool get _isMulti => questionType == 'multiple_choice';

  @override
  Widget build(BuildContext context) {
    final byIndex = {for (final o in options) o.orderIndex: o};
    final order = displayOrder ?? options.map((o) => o.orderIndex).toList();
    final correct =
        result == null ? const <int>{} : result!.correctIndexes.toSet();
    final interactive = enabled && result == null;

    return Column(
      children: [
        for (final oi in order)
          if (byIndex[oi] != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _OptionRow(
                option: byIndex[oi]!,
                selected: selectedIndexes.contains(oi),
                multi: _isMulti,
                languageMode: languageMode,
                enabled: interactive,
                borderColor: _borderColor(oi, correct),
                borderWidth:
                    result == null && selectedIndexes.contains(oi) ? 1.5 : 1,
                bgColor: _bgColor(oi, correct),
                trailing: _resultIcon(oi, correct),
                onTap: () {
                  if (!interactive) return;
                  onToggle(oi);
                },
              ),
            ),
      ],
    );
  }

  Color _borderColor(int oi, Set<int> correct) {
    if (result == null) {
      return selectedIndexes.contains(oi) ? AppColors.primary : AppColors.border;
    }
    if (correct.contains(oi)) return AppColors.success;
    if (selectedIndexes.contains(oi)) return AppColors.destructive;
    return AppColors.border;
  }

  Color? _bgColor(int oi, Set<int> correct) {
    if (result == null) return null;
    if (correct.contains(oi)) return AppColors.success.withValues(alpha: 0.1);
    if (selectedIndexes.contains(oi)) {
      return AppColors.destructive.withValues(alpha: 0.1);
    }
    return null;
  }

  Widget? _resultIcon(int oi, Set<int> correct) {
    if (result == null) return null;
    if (correct.contains(oi)) {
      return const Icon(Icons.check_circle, color: AppColors.success, size: 20);
    }
    if (selectedIndexes.contains(oi)) {
      return const Icon(Icons.cancel, color: AppColors.destructive, size: 20);
    }
    return null;
  }
}

class _OptionRow extends StatelessWidget {
  const _OptionRow({
    required this.option,
    required this.selected,
    required this.multi,
    required this.languageMode,
    required this.enabled,
    required this.borderColor,
    required this.borderWidth,
    required this.onTap,
    this.bgColor,
    this.trailing,
  });

  final OptionDelivery option;
  final bool selected;
  final bool multi;
  final String languageMode;
  final bool enabled;
  final Color borderColor;
  final double borderWidth;
  final Color? bgColor;
  final Widget? trailing;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: bgColor ?? AppColors.card,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: borderColor, width: borderWidth),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (multi)
                Checkbox(
                  value: selected,
                  onChanged: enabled ? (_) => onTap() : null,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                )
              else
                Radio<bool>(
                  value: true,
                  groupValue: selected ? true : null,
                  onChanged: enabled ? (_) => onTap() : null,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                ),
              const SizedBox(width: 8),
              Expanded(
                child: BilingualText(
                  text: option.content,
                  mode: languageMode,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: 8),
                trailing!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}
