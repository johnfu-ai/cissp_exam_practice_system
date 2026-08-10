import 'package:cissp_compass/core/cookie.dart';
import 'package:dio/dio.dart';
import 'package:test/test.dart';

void main() {
  group('extractRefreshToken', () {
    test('parses single Set-Cookie', () {
      final headers = Headers.fromMap({
        'set-cookie': [
          'refresh_token=abc123; HttpOnly; Path=/api/auth; SameSite=lax',
        ],
      });
      expect(extractRefreshToken(headers), 'abc123');
    });

    test('ignores unrelated cookies', () {
      final headers = Headers.fromMap({
        'set-cookie': [
          'other=1; Path=/',
          'refresh_token=xyz; HttpOnly; Path=/api/auth',
        ],
      });
      expect(extractRefreshToken(headers), 'xyz');
    });

    test('returns null when missing', () {
      final headers = Headers.fromMap({
        'set-cookie': ['session=1; Path=/'],
      });
      expect(extractRefreshToken(headers), isNull);
    });
  });
}
