// Pure presentation helpers for exam (and shared) timing / percentages.

/// Format a millisecond countdown as `H:MM:SS` (or `MM:SS` under an hour).
String fmtCountdown(int ms) {
  final total = (ms < 0 ? 0 : ms) ~/ 1000;
  final h = total ~/ 3600;
  final m = (total % 3600) ~/ 60;
  final s = total % 60;
  final mm = m.toString().padLeft(2, '0');
  final ss = s.toString().padLeft(2, '0');
  if (h > 0) return '$h:$mm:$ss';
  return '$mm:$ss';
}

/// True when remaining time is in the final warning window (≤ 5 min).
bool isTimeCritical(int ms) => ms <= 5 * 60 * 1000;

/// Format a 0–1 accuracy ratio as a percent string.
String fmtPct(double n) => '${(n * 100).round()}%';

/// Human duration from milliseconds (`45s`, `1m 30s`, `1h 0m`).
String fmtDuration(int ms) {
  final totalSec = (ms / 1000).round();
  final h = totalSec ~/ 3600;
  final m = (totalSec % 3600) ~/ 60;
  final s = totalSec % 60;
  if (h > 0) return '${h}h ${m}m';
  if (m > 0) return '${m}m ${s}s';
  return '${s}s';
}
