import 'package:dio/dio.dart';

import 'package:cissp_compass/core/config.dart';
import 'package:cissp_compass/core/cookie.dart';

typedef AccessTokenGetter = String? Function();
typedef RefreshOnce = Future<String?> Function();
typedef PersistRefresh = Future<void> Function(String token);

bool isAuthCredentialPath(String path) {
  return path.contains('/api/auth/login') ||
      path.contains('/api/auth/register') ||
      path.contains('/api/auth/refresh');
}

/// Build the shared Dio with Bearer auth, 401 singleton refresh, and cookie capture.
Dio createAppDio({
  ApiConfig config = ApiConfig.current,
  required AccessTokenGetter getAccessToken,
  required RefreshOnce refreshOnce,
  required PersistRefresh persistRefresh,
  Dio? dio,
}) {
  final client = dio ?? Dio();
  client.options = BaseOptions(
    baseUrl: config.apiBaseUrl,
    connectTimeout: const Duration(seconds: 20),
    receiveTimeout: const Duration(seconds: 60),
    headers: const {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
    validateStatus: (s) => s != null && s >= 200 && s < 400,
  );

  client.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final token = getAccessToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onResponse: (response, handler) async {
        final path = response.requestOptions.path;
        if (isAuthCredentialPath(path)) {
          final refresh = extractRefreshToken(response.headers);
          if (refresh != null) {
            await persistRefresh(refresh);
          }
        }
        handler.next(response);
      },
      onError: (err, handler) async {
        final status = err.response?.statusCode;
        final path = err.requestOptions.path;
        final retried = err.requestOptions.extra['auth_retried'] == true;

        if (status == 401 && !retried && !isAuthCredentialPath(path)) {
          final newAccess = await refreshOnce();
          if (newAccess != null && newAccess.isNotEmpty) {
            final req = err.requestOptions;
            req.headers['Authorization'] = 'Bearer $newAccess';
            req.extra['auth_retried'] = true;
            try {
              final response = await client.fetch(req);
              return handler.resolve(response);
            } catch (e) {
              if (e is DioException) {
                return handler.next(e);
              }
              return handler.next(err);
            }
          }
        }

        // Still capture Set-Cookie on auth error responses if present.
        final headers = err.response?.headers;
        if (headers != null && isAuthCredentialPath(path)) {
          final refresh = extractRefreshToken(headers);
          if (refresh != null) {
            await persistRefresh(refresh);
          }
        }
        handler.next(err);
      },
    ),
  );

  return client;
}
