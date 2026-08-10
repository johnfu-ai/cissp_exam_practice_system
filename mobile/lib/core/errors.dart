import 'package:dio/dio.dart';

/// Mapped HTTP / transport failure from the FastAPI backend.
class ApiException implements Exception {
  ApiException({required this.status, required this.message});

  final int status;
  final String message;

  @override
  String toString() => 'ApiException($status): $message';

  /// Parse Dio errors into a stable [ApiException].
  ///
  /// FastAPI typically returns `{ "detail": "..." }` or
  /// `{ "detail": [ { "msg": "..." }, ... ] }`.
  factory ApiException.fromDio(DioException e) {
    final status = e.response?.statusCode ?? 0;
    final data = e.response?.data;
    final detail = _parseDetail(data);
    if (detail != null && detail.isNotEmpty) {
      return ApiException(status: status, message: detail);
    }
    if (e.message != null && e.message!.isNotEmpty) {
      return ApiException(status: status, message: e.message!);
    }
    return ApiException(status: status, message: e.type.name);
  }

  static String? _parseDetail(dynamic data) {
    if (data == null) return null;
    if (data is String) return data;
    if (data is! Map) return data.toString();
    final detail = data['detail'];
    if (detail == null) return null;
    if (detail is String) return detail;
    if (detail is List) {
      final parts = <String>[];
      for (final item in detail) {
        if (item is String) {
          parts.add(item);
        } else if (item is Map) {
          final msg = item['msg'] ?? item['message'] ?? item['detail'];
          if (msg != null) parts.add(msg.toString());
        } else {
          parts.add(item.toString());
        }
      }
      return parts.isEmpty ? null : parts.join('; ');
    }
    return detail.toString();
  }
}
