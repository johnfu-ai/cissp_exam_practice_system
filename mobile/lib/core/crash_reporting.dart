import 'package:flutter/foundation.dart';

/// Crash + error reporting seam (runtime-hardening item #4).
///
/// The app previously had no global error hooks and many silent
/// `catch (_) {}` swallows, so failures on real devices were invisible.
/// Everything now funnels through [CrashReporter.current]:
///
/// - [installGlobalHandlers] routes framework errors ([FlutterError.onError])
///   and uncaught platform-dispatcher errors
///   ([PlatformDispatcher.instance.onError]) into the reporter.
/// - `main()` wraps `runApp` in `runZonedGuarded` as belt-and-braces.
/// - [logError] is the replacement for silent catch blocks — same behavior
///   (swallow and degrade) but the failure is recorded, not lost.
///
/// The default [LogCrashReporter] writes to the debug log only. To ship real
/// crash reporting, attach a Sentry/Crashlytics-backed implementation before
/// `runApp` (no other call sites change):
///
/// ```dart
/// CrashReporter.attach(SentryCrashReporter(dsn: ...));
/// CrashReporter.installGlobalHandlers();
/// ```
abstract class CrashReporter {
  static CrashReporter current = LogCrashReporter();

  /// Swap the implementation (e.g. Sentry-backed). Call before runApp.
  static void attach(CrashReporter reporter) {
    current = reporter;
  }

  /// Route framework + platform errors into [current]. Call once at startup.
  static void installGlobalHandlers() {
    FlutterError.onError = (details) {
      current.recordError(
        details.exception,
        details.stack,
        context: details.library ?? 'flutter',
        fatal: details.informationCollector == null && kReleaseMode,
      );
      // Keep the default console rendering in debug/test builds.
      if (kDebugMode) {
        FlutterError.presentError(details);
      }
    };
    PlatformDispatcher.instance.onError = (error, stack) {
      current.recordError(error, stack, fatal: true);
      return true; // Handled: do not crash the runner.
    };
  }

  void recordError(
    Object error,
    StackTrace? stackTrace, {
    String? context,
    bool fatal = false,
  });

  void log(String message);
}

/// Records errors to the debug log (default, dependency-free implementation).
class LogCrashReporter implements CrashReporter {
  @override
  void recordError(
    Object error,
    StackTrace? stackTrace, {
    String? context,
    bool fatal = false,
  }) {
    debugPrint(
      '[crash${fatal ? ':fatal' : ''}]${context != null ? ' $context' : ''} '
      '$error${stackTrace != null ? '\n$stackTrace' : ''}',
    );
  }

  @override
  void log(String message) {
    debugPrint('[crash] $message');
  }
}

/// Replacement for silent `catch (_) {}` blocks: keeps the degrade-and-surface
/// behavior but records the failure through [CrashReporter.current].
void logError(Object error, StackTrace stackTrace, String context) {
  CrashReporter.current.recordError(error, stackTrace, context: context);
}
