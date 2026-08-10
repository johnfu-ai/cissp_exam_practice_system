import 'package:cissp_api/cissp_api.dart';

/// One displayable taxonomy label from [AnswerResult.mapping].
/// Values are raw taxonomy strings (not translated — FR-I18N-05).
class MappingLabel {
  final String kind; // domain | chapter | knowledge_point
  final String value;
  const MappingLabel({required this.kind, required this.value});
}

String? _firstNonEmptyString(JsonMap map, List<String> keys) {
  for (final key in keys) {
    final v = map[key];
    if (v is String && v.trim().isNotEmpty) return v.trim();
  }
  return null;
}

/// Prefer human names from the answer mapping payload; ignore bare UUID ids.
List<MappingLabel> mappingLabelsFrom(JsonMap mapping) {
  final out = <MappingLabel>[];
  final domain = _firstNonEmptyString(mapping, const [
    'domain_name',
    'domain',
  ]);
  if (domain != null) {
    out.add(MappingLabel(kind: 'domain', value: domain));
  }
  final chapter = _firstNonEmptyString(mapping, const [
    'chapter_title',
    'chapter_name',
    'chapter',
  ]);
  if (chapter != null) {
    out.add(MappingLabel(kind: 'chapter', value: chapter));
  }
  final kp = _firstNonEmptyString(mapping, const [
    'knowledge_point_name',
    'knowledge_point',
    'kp_name',
  ]);
  if (kp != null) {
    out.add(MappingLabel(kind: 'knowledge_point', value: kp));
  }
  return out;
}

class HistoryAttempt {
  final bool isCorrect;
  final DateTime? answeredAt;
  const HistoryAttempt({required this.isCorrect, this.answeredAt});
}

List<HistoryAttempt> historyAttemptsFrom(List<JsonMap> history) {
  return [
    for (final row in history)
      HistoryAttempt(
        isCorrect: row['is_correct'] as bool? ?? false,
        answeredAt: _parseIso(row['answered_at'] as String?),
      ),
  ];
}

DateTime? _parseIso(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  return DateTime.tryParse(raw)?.toLocal();
}

/// Compact relative past for prior attempts (English tokens; UI may wrap).
String formatRelativePast(DateTime when, DateTime now) {
  final d = now.difference(when);
  if (d.isNegative || d.inSeconds < 45) return 'just now';
  if (d.inMinutes < 60) return '${d.inMinutes}m ago';
  if (d.inHours < 24) return '${d.inHours}h ago';
  if (d.inDays < 30) return '${d.inDays}d ago';
  final y = when.year.toString().padLeft(4, '0');
  final m = when.month.toString().padLeft(2, '0');
  final day = when.day.toString().padLeft(2, '0');
  return '$y-$m-$day';
}
