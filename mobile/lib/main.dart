import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:cissp_compass/app.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/core/storage.dart';
import 'package:cissp_compass/locale_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final shared = await SharedPreferences.getInstance();
  final prefs = SharedPrefsStore(shared);
  final cachedLang = await prefs.getInterfaceLanguage() ?? 'en';

  final container = ProviderContainer(
    overrides: [
      prefsStoreProvider.overrideWithValue(prefs),
      initialLocaleProvider.overrideWithValue(cachedLang),
    ],
  );

  // Restore session before first frame so redirect sees hydrated auth.
  await container.read(authSessionProvider.notifier).hydrate();

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const CisspApp(),
    ),
  );
}
