import 'package:cissp_api/cissp_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:cissp_compass/core/auth_session.dart';
import 'package:cissp_compass/core/storage.dart';

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

/// Overridden in [main] with a [SharedPrefsStore] after prefs load.
final prefsStoreProvider = Provider<PrefsStore>((ref) {
  throw StateError(
    'prefsStoreProvider must be overridden with SharedPrefsStore in main()',
  );
});

final authSessionProvider =
    StateNotifierProvider<AuthSession, AuthState>((ref) {
  return AuthSession(
    tokenStore: ref.watch(tokenStoreProvider),
    prefsStore: ref.watch(prefsStoreProvider),
  );
});

final dioProvider = Provider<Dio>((ref) {
  return ref.watch(authSessionProvider.notifier).dio;
});

final cisspApiProvider = Provider<CisspApi>((ref) {
  return ref.watch(authSessionProvider.notifier).api;
});
