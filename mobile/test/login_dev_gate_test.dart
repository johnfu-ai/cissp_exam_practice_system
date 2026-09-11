import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/features/auth/login_screen.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _app() {
  return MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    locale: const Locale('en'),
    home: const Scaffold(body: LoginScreen()),
  );
}

void main() {
  testWidgets('dev-login shortcut hidden in production builds', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [devConveniencesProvider.overrideWithValue(false)],
        child: _app(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Dev login (admin)'), findsNothing);
    // The real login affordances remain.
    expect(find.text('Log in'), findsOneWidget);
  });

  testWidgets('dev-login shortcut visible in development builds', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [devConveniencesProvider.overrideWithValue(true)],
        child: _app(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Dev login (admin)'), findsOneWidget);
  });
}
