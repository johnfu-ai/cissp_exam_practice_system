import 'package:cissp_compass/core/crash_reporting.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _MemoryReporter implements CrashReporter {
  final List<String> events = [];

  @override
  void recordError(
    Object error,
    StackTrace? stackTrace, {
    String? context,
    bool fatal = false,
  }) {
    events.add('error:$context:$fatal:$error');
  }

  @override
  void log(String message) {
    events.add('log:$message');
  }
}

void main() {
  tearDown(() {
    // Restore the default reporter + framework handlers for other tests.
    CrashReporter.attach(LogCrashReporter());
  });

  test('logError routes through CrashReporter.current', () {
    final mem = _MemoryReporter();
    CrashReporter.attach(mem);
    logError(StateError('boom'), StackTrace.empty, 'login:submit');
    expect(mem.events, contains('error:login:submit:false:Bad state: boom'));
  });

  testWidgets('installGlobalHandlers routes framework errors', (tester) async {
    final mem = _MemoryReporter();
    CrashReporter.attach(mem);

    final previousHandler = FlutterError.onError;
    CrashReporter.installGlobalHandlers();
    try {
      FlutterError.reportError(FlutterErrorDetails(
        exception: StateError('widget boom'),
        library: 'login screen',
        stack: StackTrace.empty,
      ));
      expect(
        mem.events,
        contains(contains('error:login screen:')),
      );
      expect(mem.events.first, contains('widget boom'));
    } finally {
      FlutterError.onError = previousHandler;
    }
  });
}
