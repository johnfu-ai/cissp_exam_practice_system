import 'package:test/test.dart';

import 'package:cissp_compass/core/config.dart';

void main() {
  group('resolveAppEnv', () {
    test('production resolves to AppEnv.production', () {
      expect(resolveAppEnv('production'), AppEnv.production);
    });

    test('is case- and whitespace-insensitive', () {
      expect(resolveAppEnv(' Production '), AppEnv.production);
      expect(resolveAppEnv('PRODUCTION'), AppEnv.production);
    });

    test('unknown, empty, and null values fall back to development', () {
      // Fail-safe: a typo must never ship a "production" build that still
      // shows dev affordances.
      expect(resolveAppEnv('prod'), AppEnv.development);
      expect(resolveAppEnv('staging'), AppEnv.development);
      expect(resolveAppEnv(''), AppEnv.development);
      expect(resolveAppEnv(null), AppEnv.development);
    });
  });

  group('ApiConfig.enableDevConveniences', () {
    test('development build keeps dev conveniences', () {
      const config = ApiConfig(
        apiBaseUrl: 'http://10.0.2.2:8000',
        appEnvRaw: 'development',
      );
      expect(config.isProduction, isFalse);
      expect(config.enableDevConveniences, isTrue);
    });

    test('production build compiles out dev conveniences', () {
      const config = ApiConfig(
        apiBaseUrl: 'https://api.example.com',
        appEnvRaw: 'production',
      );
      expect(config.isProduction, isTrue);
      expect(config.enableDevConveniences, isFalse);
    });

    test('compile-time default is development (dev loopback base URL)', () {
      expect(ApiConfig.current.appEnv, AppEnv.development);
      expect(ApiConfig.current.enableDevConveniences, isTrue);
    });
  });
}
