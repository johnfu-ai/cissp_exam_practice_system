import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Opaque refresh-token persistence (secure on device, in-memory in tests).
abstract class TokenStore {
  Future<String?> getRefreshToken();
  Future<void> setRefreshToken(String token);
  Future<void> clearRefreshToken();
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'refresh_token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> getRefreshToken() => _storage.read(key: _key);

  @override
  Future<void> setRefreshToken(String token) =>
      _storage.write(key: _key, value: token);

  @override
  Future<void> clearRefreshToken() => _storage.delete(key: _key);
}

class MemoryTokenStore implements TokenStore {
  String? _token;

  @override
  Future<String?> getRefreshToken() async => _token;

  @override
  Future<void> setRefreshToken(String token) async => _token = token;

  @override
  Future<void> clearRefreshToken() async => _token = null;
}

/// UI prefs + local resume trackers (not secrets).
abstract class PrefsStore {
  Future<String?> getInterfaceLanguage();
  Future<void> setInterfaceLanguage(String value);

  Future<String?> getLanguageMode();
  Future<void> setLanguageMode(String value);

  Future<List<String>> getPracticeSessionIds();
  Future<void> setPracticeSessionIds(List<String> ids);

  Future<List<String>> getExamSessionIds();
  Future<void> setExamSessionIds(List<String> ids);
}

class SharedPrefsStore implements PrefsStore {
  SharedPrefsStore(this._prefs);

  static const _kInterfaceLanguage = 'interface_language';
  static const _kLanguageMode = 'language_mode';
  static const _kPracticeSessions = 'practice_active_sessions';
  static const _kExamSessions = 'exam_active_sessions';

  final SharedPreferences _prefs;

  @override
  Future<String?> getInterfaceLanguage() async =>
      _prefs.getString(_kInterfaceLanguage);

  @override
  Future<void> setInterfaceLanguage(String value) async {
    await _prefs.setString(_kInterfaceLanguage, value);
  }

  @override
  Future<String?> getLanguageMode() async => _prefs.getString(_kLanguageMode);

  @override
  Future<void> setLanguageMode(String value) async {
    await _prefs.setString(_kLanguageMode, value);
  }

  @override
  Future<List<String>> getPracticeSessionIds() async =>
      _readJsonList(_kPracticeSessions);

  @override
  Future<void> setPracticeSessionIds(List<String> ids) async {
    await _prefs.setString(_kPracticeSessions, jsonEncode(ids));
  }

  @override
  Future<List<String>> getExamSessionIds() async =>
      _readJsonList(_kExamSessions);

  @override
  Future<void> setExamSessionIds(List<String> ids) async {
    await _prefs.setString(_kExamSessions, jsonEncode(ids));
  }

  List<String> _readJsonList(String key) {
    final raw = _prefs.getString(key);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final parsed = jsonDecode(raw);
      if (parsed is! List) return const [];
      return parsed.whereType<String>().toList();
    } catch (_) {
      return const [];
    }
  }
}

class MemoryPrefsStore implements PrefsStore {
  String? interfaceLanguage;
  String? languageMode;
  List<String> practiceSessionIds = [];
  List<String> examSessionIds = [];

  @override
  Future<String?> getInterfaceLanguage() async => interfaceLanguage;

  @override
  Future<void> setInterfaceLanguage(String value) async {
    interfaceLanguage = value;
  }

  @override
  Future<String?> getLanguageMode() async => languageMode;

  @override
  Future<void> setLanguageMode(String value) async {
    languageMode = value;
  }

  @override
  Future<List<String>> getPracticeSessionIds() async =>
      List<String>.from(practiceSessionIds);

  @override
  Future<void> setPracticeSessionIds(List<String> ids) async {
    practiceSessionIds = List<String>.from(ids);
  }

  @override
  Future<List<String>> getExamSessionIds() async =>
      List<String>.from(examSessionIds);

  @override
  Future<void> setExamSessionIds(List<String> ids) async {
    examSessionIds = List<String>.from(ids);
  }
}
