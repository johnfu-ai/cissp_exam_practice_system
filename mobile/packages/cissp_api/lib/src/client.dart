import 'package:dio/dio.dart';

import 'models.dart';

/// Thin FastAPI learner client. Auth headers / refresh are injected by the app.
class CisspApi {
  CisspApi(this.dio);

  final Dio dio;

  Future<TokenOut> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    final r = await dio.post<JsonMap>(
      '/api/auth/register',
      data: {
        'email': email,
        'password': password,
        if (displayName != null) 'display_name': displayName,
      },
    );
    return TokenOut.fromJson(r.data!);
  }

  Future<TokenOut> login({required String email, required String password}) async {
    final r = await dio.post<JsonMap>(
      '/api/auth/login',
      data: {'email': email, 'password': password},
    );
    return TokenOut.fromJson(r.data!);
  }

  Future<TokenOut> refresh({String? refreshToken}) async {
    final r = await dio.post<JsonMap>(
      '/api/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    return TokenOut.fromJson(r.data!);
  }

  Future<void> logout({String? refreshToken, String? accessToken}) async {
    await dio.post(
      '/api/auth/logout',
      data: {
        if (refreshToken != null) 'refresh_token': refreshToken,
        if (accessToken != null) 'access_token': accessToken,
      },
    );
  }

  Future<UserOut> me() async {
    final r = await dio.get<JsonMap>('/api/auth/me');
    return UserOut.fromJson(r.data!);
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await dio.put(
      '/api/auth/password',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
  }

  Future<JsonMap> requestPasswordReset(String email) async {
    final r = await dio.post<JsonMap>(
      '/api/auth/reset-password/request',
      data: {'email': email},
    );
    return r.data!;
  }

  Future<void> confirmPasswordReset({
    required String token,
    required String newPassword,
  }) async {
    await dio.post(
      '/api/auth/reset-password/confirm',
      data: {'token': token, 'new_password': newPassword},
    );
  }

  Future<Preferences> getPreferences() async {
    final r = await dio.get<JsonMap>('/api/users/me/preferences');
    return Preferences.fromJson(r.data!);
  }

  Future<Preferences> putPreferences({
    String? languageMode,
    String? interfaceLanguage,
    DateTime? examTargetDate,
    bool updateExamTargetDate = false,
    int? dailyGoalAnswers,
    bool updateDailyGoal = false,
  }) async {
    final r = await dio.put<JsonMap>(
      '/api/users/me/preferences',
      data: {
        if (languageMode != null) 'language_mode': languageMode,
        if (interfaceLanguage != null) 'interface_language': interfaceLanguage,
        // The update* flags send the goal fields even when null, which the
        // API treats as "clear the goal" (absent field = leave unchanged).
        if (updateExamTargetDate)
          'exam_target_date':
              examTargetDate?.toIso8601String().substring(0, 10),
        if (updateDailyGoal) 'daily_goal_answers': dailyGoalAnswers,
      },
    );
    return Preferences.fromJson(r.data!);
  }

  Future<List<DomainOut>> domains() async {
    final r = await dio.get<List>('/api/domains');
    return r.data!.map((e) => DomainOut.fromJson(e as JsonMap)).toList();
  }

  Future<List<BookOut>> books() async {
    final r = await dio.get<List>('/api/books');
    return r.data!.map((e) => BookOut.fromJson(e as JsonMap)).toList();
  }

  Future<List<ChapterOut>> chapters(String bookId) async {
    final r = await dio.get<List>('/api/books/$bookId/chapters');
    return r.data!.map((e) => ChapterOut.fromJson(e as JsonMap)).toList();
  }

  Future<List<TagOut>> tags() async {
    final r = await dio.get<List>('/api/tags');
    return r.data!.map((e) => TagOut.fromJson(e as JsonMap)).toList();
  }

  Future<SessionOut> createPractice(JsonMap body) async {
    final r = await dio.post<JsonMap>('/api/practice/sessions', data: body);
    return SessionOut.fromJson(r.data!);
  }

  Future<SessionOut> getPractice(String id) async {
    final r = await dio.get<JsonMap>('/api/practice/sessions/$id');
    return SessionOut.fromJson(r.data!);
  }

  Future<QuestionDelivery> practiceQuestion(String id, int position) async {
    final r = await dio.get<JsonMap>('/api/practice/sessions/$id/questions/$position');
    return QuestionDelivery.fromJson(r.data!);
  }

  Future<AnswerResult> submitPracticeAnswer(String id, JsonMap body) async {
    final r = await dio.post<JsonMap>('/api/practice/sessions/$id/answers', data: body);
    return AnswerResult.fromJson(r.data!);
  }

  Future<SessionOut> pausePractice(String id) async {
    final r = await dio.post<JsonMap>('/api/practice/sessions/$id/pause');
    return SessionOut.fromJson(r.data!);
  }

  Future<SessionOut> resumePractice(String id) async {
    final r = await dio.post<JsonMap>('/api/practice/sessions/$id/resume');
    return SessionOut.fromJson(r.data!);
  }

  Future<SessionSummary> finishPractice(String id) async {
    final r = await dio.post<JsonMap>('/api/practice/sessions/$id/finish');
    return SessionSummary.fromJson(r.data!);
  }

  Future<SessionSummary> practiceSummary(String id) async {
    final r = await dio.get<JsonMap>('/api/practice/sessions/$id/summary');
    return SessionSummary.fromJson(r.data!);
  }

  Future<QuestionState> putQuestionState(String questionId, JsonMap body) async {
    final r = await dio.put<JsonMap>('/api/practice/questions/$questionId/state', data: body);
    return QuestionState.fromJson(r.data!);
  }

  Future<List<RelatedQuestion>> relatedQuestions(String questionId) async {
    final r = await dio.get<List>('/api/practice/questions/$questionId/related');
    return r.data!.map((e) => RelatedQuestion.fromJson(e as JsonMap)).toList();
  }

  Future<ExamSession> createExam(JsonMap body) async {
    final r = await dio.post<JsonMap>('/api/exam/sessions', data: body);
    return ExamSession.fromJson(r.data!);
  }

  Future<ExamSession> getExam(String id) async {
    final r = await dio.get<JsonMap>('/api/exam/sessions/$id');
    return ExamSession.fromJson(r.data!);
  }

  Future<QuestionDelivery> examQuestion(String id, int position) async {
    final r = await dio.get<JsonMap>('/api/exam/sessions/$id/questions/$position');
    return QuestionDelivery.fromJson(r.data!);
  }

  Future<QuestionDelivery> examNext(String id) async {
    final r = await dio.get<JsonMap>('/api/exam/sessions/$id/next');
    return QuestionDelivery.fromJson(r.data!);
  }

  Future<ExamAnswerAck> submitExamAnswer(String id, JsonMap body) async {
    final r = await dio.post<JsonMap>('/api/exam/sessions/$id/answers', data: body);
    return ExamAnswerAck.fromJson(r.data!);
  }

  Future<ExamReport> finishExam(String id) async {
    final r = await dio.post<JsonMap>('/api/exam/sessions/$id/finish');
    return ExamReport.fromJson(r.data!);
  }

  Future<ExamReport> examReport(String id) async {
    final r = await dio.get<JsonMap>('/api/exam/sessions/$id/report');
    return ExamReport.fromJson(r.data!);
  }

  Future<List<ReviewItem>> examReview(String id) async {
    final r = await dio.get<List>('/api/exam/sessions/$id/review');
    return r.data!.map((e) => ReviewItem.fromJson(e as JsonMap)).toList();
  }

  Future<List<ExamHistoryItem>> examHistory({int limit = 20, int offset = 0}) async {
    final r = await dio.get<List>(
      '/api/exam/history',
      queryParameters: {'limit': limit, 'offset': offset},
    );
    return r.data!.map((e) => ExamHistoryItem.fromJson(e as JsonMap)).toList();
  }

  Future<DashboardOut> dashboard() async {
    final r = await dio.get<JsonMap>('/api/analytics/dashboard');
    return DashboardOut.fromJson(r.data!);
  }

  Future<List<DomainMastery>> domainMastery() async {
    final r = await dio.get<List>('/api/analytics/domains');
    return r.data!.map((e) => DomainMastery.fromJson(e as JsonMap)).toList();
  }

  Future<TrendOut> trend({int windowDays = 30}) async {
    final r = await dio.get<JsonMap>(
      '/api/analytics/trend',
      queryParameters: {'window_days': windowDays},
    );
    return TrendOut.fromJson(r.data!);
  }

  Future<WeakAreasOut> weakAreas() async {
    final r = await dio.get<JsonMap>('/api/analytics/weak-areas');
    return WeakAreasOut.fromJson(r.data!);
  }

  Future<ErrorTypeOut> errorTypes() async {
    final r = await dio.get<JsonMap>('/api/analytics/error-types');
    return ErrorTypeOut.fromJson(r.data!);
  }

  Future<ReviewRecommendation> recommendation() async {
    final r = await dio.get<JsonMap>('/api/analytics/recommendation');
    return ReviewRecommendation.fromJson(r.data!);
  }
}
