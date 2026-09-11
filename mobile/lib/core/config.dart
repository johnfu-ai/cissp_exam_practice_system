/// Build environment of the compiled app.
enum AppEnv { development, production }

/// Maps a raw `APP_ENV` dart-define value to an [AppEnv].
///
/// Unknown or missing values resolve to [AppEnv.development] so a typo can
/// never produce a "production" build that still shows dev affordances —
/// only an explicit `production` hides them.
AppEnv resolveAppEnv(String? raw) {
  return raw?.trim().toLowerCase() == 'production'
      ? AppEnv.production
      : AppEnv.development;
}

/// Runtime API configuration (overridable via `--dart-define`).
///
/// Build-time knobs:
/// - `API_BASE_URL` — backend origin (default is the Android emulator
///   loopback, `10.0.2.2`).
/// - `APP_ENV` — `development` (default) or `production`. Release builds
///   for distribution must pass `--dart-define=APP_ENV=production`, which
///   compiles out dev conveniences (dev-login shortcut, dev reset-token
///   display).
class ApiConfig {
  const ApiConfig({
    required this.apiBaseUrl,
    this.appEnvRaw = 'development',
  });

  /// Backend origin. Android emulator loopback default is `10.0.2.2`.
  final String apiBaseUrl;

  /// Raw `APP_ENV` value baked in at compile time.
  final String appEnvRaw;

  AppEnv get appEnv => resolveAppEnv(appEnvRaw);

  bool get isProduction => appEnv == AppEnv.production;

  /// Dev affordances (dev-login button, showing the raw password-reset
  /// token) only render in non-production builds.
  bool get enableDevConveniences => !isProduction;

  static const current = ApiConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
    appEnvRaw: String.fromEnvironment(
      'APP_ENV',
      defaultValue: 'development',
    ),
  );
}
