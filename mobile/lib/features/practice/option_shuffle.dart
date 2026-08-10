/// Deterministic seeded Fisher–Yates over option [order_index] values.
///
/// Display order varies per [questionId]; selection/submit stay canonical
/// `order_index` (mirrors the web `shuffleBySeed` algorithm).
List<int> shuffledOrderIndexes(List<int> orderIndexes, String questionId) {
  final out = List<int>.from(orderIndexes);
  var state = _seedHash(questionId);
  for (var i = out.length - 1; i > 0; i--) {
    state ^= (state << 13) & 0xFFFFFFFF;
    state ^= (state >> 17) & 0xFFFFFFFF;
    state ^= (state << 5) & 0xFFFFFFFF;
    state &= 0xFFFFFFFF;
    final j = state % (i + 1);
    final tmp = out[i];
    out[i] = out[j];
    out[j] = tmp;
  }
  return out;
}

/// Convenience: map options → display-order list of `order_index`.
List<int> displayOrderIndexes(
  Iterable<int> orderIndexes,
  String questionId, {
  bool shuffle = true,
}) {
  final list = orderIndexes.toList();
  if (!shuffle) return list;
  return shuffledOrderIndexes(list, questionId);
}

int _seedHash(String seed) {
  // FNV-1a 32-bit, matching the web runner's xorshift seed.
  var h = 2166136261;
  for (final cu in seed.codeUnits) {
    h ^= cu;
    h = _imul(h, 16777619) & 0xFFFFFFFF;
  }
  h &= 0xFFFFFFFF;
  return h == 0 ? 1 : h;
}

/// JS `Math.imul` equivalent (32-bit signed multiply, returned as unsigned).
int _imul(int a, int b) {
  final ah = (a >> 16) & 0xffff;
  final al = a & 0xffff;
  final bh = (b >> 16) & 0xffff;
  final bl = b & 0xffff;
  final mixed = ((al * bh + ah * bl) & 0xffff) << 16;
  return (mixed + al * bl) & 0xFFFFFFFF;
}
