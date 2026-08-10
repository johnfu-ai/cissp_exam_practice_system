import 'package:cissp_api/cissp_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:cissp_compass/core/api_provider.dart';
import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/refresh_gate.dart';
import 'package:cissp_compass/core/storage.dart';

class AuthState {
  const AuthState({
    this.user,
    this.accessToken,
    this.hydrated = false,
  });

  final UserOut? user;
  final String? accessToken;
  final bool hydrated;

  bool get isAuthenticated =>
      accessToken != null && accessToken!.isNotEmpty && user != null;

  AuthState copyWith({
    UserOut? user,
    String? accessToken,
    bool? hydrated,
    bool clearUser = false,
    bool clearAccess = false,
  }) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      accessToken: clearAccess ? null : (accessToken ?? this.accessToken),
      hydrated: hydrated ?? this.hydrated,
    );
  }
}

/// In-memory access token + user; refresh token lives in [TokenStore].
class AuthSession extends StateNotifier<AuthState> {
  AuthSession({
    required TokenStore tokenStore,
    required PrefsStore prefsStore,
    Dio? dio,
    CisspApi? api,
  })  : _tokens = tokenStore,
        _prefs = prefsStore,
        super(const AuthState()) {
    _dio = dio ??
        createAppDio(
          getAccessToken: () => state.accessToken,
          refreshOnce: refreshOnce,
          persistRefresh: persistRefresh,
        );
    _api = api ?? CisspApi(_dio);
  }

  final TokenStore _tokens;
  final PrefsStore _prefs;
  late final Dio _dio;
  late final CisspApi _api;
  final RefreshGate<String?> _refreshGate = RefreshGate<String?>();

  Dio get dio => _dio;
  CisspApi get api => _api;
  TokenStore get tokenStore => _tokens;
  PrefsStore get prefsStore => _prefs;

  Future<void> persistRefresh(String token) => _tokens.setRefreshToken(token);

  Future<void> applyTokenOut(
    TokenOut out, {
    String? refreshFromCookie,
  }) async {
    final refresh = refreshFromCookie ?? out.refreshToken;
    if (refresh != null && refresh.isNotEmpty) {
      await _tokens.setRefreshToken(refresh);
    }
    await _prefs.setInterfaceLanguage(out.user.interfaceLanguage);
    await _prefs.setLanguageMode(out.user.languageMode);
    state = state.copyWith(user: out.user, accessToken: out.accessToken);
  }

  Future<void> hydrate() async {
    try {
      final refresh = await _tokens.getRefreshToken();
      if (refresh == null || refresh.isEmpty) {
        state = state.copyWith(hydrated: true, clearUser: true, clearAccess: true);
        return;
      }
      final access = await refreshOnce();
      if (access == null) {
        await _tokens.clearRefreshToken();
        state = state.copyWith(hydrated: true, clearUser: true, clearAccess: true);
        return;
      }
    } catch (_) {
      await _tokens.clearRefreshToken();
      state = state.copyWith(hydrated: true, clearUser: true, clearAccess: true);
      return;
    }
    state = state.copyWith(hydrated: true);
  }

  Future<void> login({required String email, required String password}) async {
    try {
      final out = await _api.login(email: email, password: password);
      await applyTokenOut(out);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    try {
      final out = await _api.register(
        email: email,
        password: password,
        displayName: displayName,
      );
      await applyTokenOut(out);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logout() async {
    final refresh = await _tokens.getRefreshToken();
    final access = state.accessToken;
    try {
      await _api.logout(refreshToken: refresh, accessToken: access);
    } catch (_) {
      // Best-effort server logout.
    }
    await _tokens.clearRefreshToken();
    state = state.copyWith(clearUser: true, clearAccess: true);
  }

  /// Return a usable access token, refreshing if needed.
  Future<String?> ensureAccess() async {
    final current = state.accessToken;
    if (current != null && current.isNotEmpty) return current;
    return refreshOnce();
  }

  /// Singleton refresh — concurrent 401s share one `/api/auth/refresh` call.
  Future<String?> refreshOnce() => _refreshGate.runOnce(_doRefresh);

  Future<String?> _doRefresh() async {
    final refresh = await _tokens.getRefreshToken();
    if (refresh == null || refresh.isEmpty) {
      state = state.copyWith(clearUser: true, clearAccess: true);
      return null;
    }
    try {
      final out = await _api.refresh(refreshToken: refresh);
      await applyTokenOut(out);
      return out.accessToken;
    } on DioException {
      await _tokens.clearRefreshToken();
      state = state.copyWith(clearUser: true, clearAccess: true);
      return null;
    } catch (_) {
      await _tokens.clearRefreshToken();
      state = state.copyWith(clearUser: true, clearAccess: true);
      return null;
    }
  }

  Future<void> setUser(UserOut user) async {
    await _prefs.setInterfaceLanguage(user.interfaceLanguage);
    await _prefs.setLanguageMode(user.languageMode);
    state = state.copyWith(user: user);
  }
}
