import 'package:dio/dio.dart';

/// Extract `refresh_token` from `Set-Cookie` response headers.
///
/// Handles multiple `set-cookie` values; value stops at the first `;`.
String? extractRefreshToken(Headers headers) {
  final values = <String>[
    ...?headers.map['set-cookie'],
    ...?headers.map['Set-Cookie'],
  ];
  for (final header in values) {
    for (final segment in header.split(',')) {
      final parts = segment.split(';');
      if (parts.isEmpty) continue;
      final pair = parts.first.trim();
      const prefix = 'refresh_token=';
      if (pair.startsWith(prefix)) {
        final value = pair.substring(prefix.length).trim();
        if (value.isNotEmpty) return value;
      }
    }
  }
  return null;
}
