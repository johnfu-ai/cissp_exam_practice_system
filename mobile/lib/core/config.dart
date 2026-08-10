/// Runtime API configuration (overridable via `--dart-define`).
class ApiConfig {
  const ApiConfig({required this.apiBaseUrl});

  /// Backend origin. Android emulator loopback default is `10.0.2.2`.
  final String apiBaseUrl;

  static const current = ApiConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
  );
}
