/// Pure MRU helpers for active practice/exam session ID lists.
///
/// Dedupes by id (most-recent first) and caps length at [max].
const int kMaxTrackedSessions = 10;

List<String> trackSessionId(
  List<String> ids,
  String id, {
  int max = kMaxTrackedSessions,
}) {
  final next = <String>[id, ...ids.where((x) => x != id)];
  if (next.length <= max) return next;
  return next.sublist(0, max);
}

List<String> untrackSessionId(List<String> ids, String id) =>
    ids.where((x) => x != id).toList();

List<String> listSessionIds(List<String> ids) => List<String>.unmodifiable(ids);
