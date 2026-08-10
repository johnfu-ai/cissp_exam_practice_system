import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:cissp_compass/core/providers.dart';

/// Drives [MaterialApp.locale] from cached prefs + optional server sync.
class LocaleController extends StateNotifier<Locale> {
  LocaleController(this._prefs, {Locale? initial})
      : super(initial ?? const Locale('en'));

  final PrefsStoreLike _prefs;

  Future<void> setInterfaceLanguage(String code) async {
    final next = Locale(code == 'zh' ? 'zh' : 'en');
    state = next;
    await _prefs.setInterfaceLanguage(next.languageCode);
    try {
      await _prefs.syncInterfaceLanguage(next.languageCode);
    } catch (_) {}
  }
}

/// Narrow surface so the controller can sync without importing API types here.
abstract class PrefsStoreLike {
  Future<void> setInterfaceLanguage(String value);
  Future<void> syncInterfaceLanguage(String value);
}

class _PrefsBridge implements PrefsStoreLike {
  _PrefsBridge(this.ref);
  final Ref ref;

  @override
  Future<void> setInterfaceLanguage(String value) =>
      ref.read(prefsStoreProvider).setInterfaceLanguage(value);

  @override
  Future<void> syncInterfaceLanguage(String value) async {
    final api = ref.read(cisspApiProvider);
    final auth = ref.read(authSessionProvider);
    if (!auth.isAuthenticated) return;
    await api.putPreferences(interfaceLanguage: value);
  }
}

final localeControllerProvider =
    StateNotifierProvider<LocaleController, Locale>((ref) {
  // Initial locale is overridden from main via [initialLocaleProvider].
  final initialCode = ref.watch(initialLocaleProvider);
  return LocaleController(
    _PrefsBridge(ref),
    initial: Locale(initialCode == 'zh' ? 'zh' : 'en'),
  );
});

/// Seeded from SharedPreferences before runApp.
final initialLocaleProvider = Provider<String>((ref) => 'en');
