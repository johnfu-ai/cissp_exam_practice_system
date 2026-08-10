/// Singleton in-flight future for concurrent 401 refresh (FR-CLIENT auth).
///
/// Pure Dart — no Flutter imports — so the concurrency contract is unit-testable
/// under `dart test -p vm`.
class RefreshGate<T> {
  Future<T>? _inflight;

  /// Share one [work] invocation across concurrent callers.
  Future<T> runOnce(Future<T> Function() work) {
    return _inflight ??= work().whenComplete(() {
      _inflight = null;
    });
  }

  bool get isInflight => _inflight != null;
}
