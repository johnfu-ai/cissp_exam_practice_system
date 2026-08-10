// Hand-maintained mirrors of FastAPI learner schemas (from openapi/openapi.json).
// Keep in sync via CI OpenAPI drift checks + manual review.

typedef JsonMap = Map<String, dynamic>;

class Localized {
  final String? en;
  final String? zh;
  const Localized({this.en, this.zh});

  factory Localized.fromJson(dynamic json) {
    if (json == null) return const Localized();
    if (json is String) return Localized(en: json);
    final m = json as JsonMap;
    return Localized(en: m['en'] as String?, zh: m['zh'] as String?);
  }

  String? pick(String mode) {
    switch (mode) {
      case 'zh':
        return zh ?? en;
      case 'en':
        return en ?? zh;
      default:
        return null;
    }
  }
}

class UserOut {
  final String id;
  final String email;
  final String? displayName;
  final List<String> roles;
  final List<String> perms;
  final String languageMode;
  final String interfaceLanguage;

  const UserOut({
    required this.id,
    required this.email,
    this.displayName,
    this.roles = const [],
    this.perms = const [],
    this.languageMode = 'en',
    this.interfaceLanguage = 'en',
  });

  factory UserOut.fromJson(JsonMap json) => UserOut(
        id: json['id'] as String,
        email: json['email'] as String,
        displayName: json['display_name'] as String?,
        roles: (json['roles'] as List? ?? const []).cast<String>(),
        perms: (json['perms'] as List? ?? const []).cast<String>(),
        languageMode: (json['language_mode'] as String?) ?? 'en',
        interfaceLanguage: (json['interface_language'] as String?) ?? 'en',
      );
}

class TokenOut {
  final String accessToken;
  final String? refreshToken;
  final String tokenType;
  final UserOut user;

  const TokenOut({
    required this.accessToken,
    this.refreshToken,
    this.tokenType = 'bearer',
    required this.user,
  });

  factory TokenOut.fromJson(JsonMap json) => TokenOut(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String?,
        tokenType: (json['token_type'] as String?) ?? 'bearer',
        user: UserOut.fromJson(json['user'] as JsonMap),
      );
}

class Preferences {
  final String languageMode;
  final String interfaceLanguage;
  const Preferences({required this.languageMode, required this.interfaceLanguage});
  factory Preferences.fromJson(JsonMap json) => Preferences(
        languageMode: json['language_mode'] as String,
        interfaceLanguage: json['interface_language'] as String,
      );
}

class DomainOut {
  final String id;
  final String blueprintId;
  final int number;
  final String name;
  final double weightPct;
  const DomainOut({
    required this.id,
    required this.blueprintId,
    required this.number,
    required this.name,
    required this.weightPct,
  });
  factory DomainOut.fromJson(JsonMap json) => DomainOut(
        id: json['id'] as String,
        blueprintId: json['blueprint_id'] as String,
        number: json['number'] as int,
        name: json['name'] as String,
        weightPct: (json['weight_pct'] as num).toDouble(),
      );
}

class BookOut {
  final String id;
  final String title;
  final String? edition;
  final String? author;
  const BookOut({required this.id, required this.title, this.edition, this.author});
  factory BookOut.fromJson(JsonMap json) => BookOut(
        id: json['id'] as String,
        title: json['title'] as String,
        edition: json['edition'] as String?,
        author: json['author'] as String?,
      );
}

class ChapterOut {
  final String id;
  final String bookId;
  final int orderIndex;
  final String title;
  const ChapterOut({
    required this.id,
    required this.bookId,
    required this.orderIndex,
    required this.title,
  });
  factory ChapterOut.fromJson(JsonMap json) => ChapterOut(
        id: json['id'] as String,
        bookId: json['book_id'] as String,
        orderIndex: json['order_index'] as int,
        title: json['title'] as String,
      );
}

class TagOut {
  final String id;
  final String name;
  final String? description;
  const TagOut({required this.id, required this.name, this.description});
  factory TagOut.fromJson(JsonMap json) => TagOut(
        id: json['id'] as String,
        name: json['name'] as String,
        description: json['description'] as String?,
      );
}

class SessionOut {
  final String id;
  final String status;
  final int totalQuestions;
  final int correctCount;
  final String startedAt;
  final String? endedAt;
  final String? pausedAt;
  final JsonMap config;
  const SessionOut({
    required this.id,
    required this.status,
    required this.totalQuestions,
    required this.correctCount,
    required this.startedAt,
    this.endedAt,
    this.pausedAt,
    this.config = const {},
  });
  factory SessionOut.fromJson(JsonMap json) => SessionOut(
        id: json['id'] as String,
        status: json['status'] as String,
        totalQuestions: json['total_questions'] as int,
        correctCount: json['correct_count'] as int,
        startedAt: json['started_at'] as String,
        endedAt: json['ended_at'] as String?,
        pausedAt: json['paused_at'] as String?,
        config: (json['config'] as JsonMap?) ?? const {},
      );
  bool get isPaused => pausedAt != null && status == 'in_progress';
}

class OptionDelivery {
  final String id;
  final int orderIndex;
  final Localized content;
  const OptionDelivery({required this.id, required this.orderIndex, required this.content});
  factory OptionDelivery.fromJson(JsonMap json) => OptionDelivery(
        id: json['id'] as String,
        orderIndex: json['order_index'] as int,
        content: Localized.fromJson(json['content']),
      );
}

class PreviousAnswer {
  final List<int> selected;
  final bool isCorrect;
  const PreviousAnswer({required this.selected, required this.isCorrect});
  factory PreviousAnswer.fromJson(JsonMap json) => PreviousAnswer(
        selected: (json['selected'] as List).cast<int>(),
        isCorrect: json['is_correct'] as bool? ?? false,
      );
}

class QuestionDelivery {
  final String sessionId;
  final int position;
  final int total;
  final String questionId;
  final String questionType;
  final List<String> availableLanguages;
  final String languageMode;
  final Localized stem;
  final List<OptionDelivery> options;
  final int elapsedMs;
  final PreviousAnswer? previousAnswer;
  final String? note;
  final int? timeRemainingMs;
  final int? difficulty;

  const QuestionDelivery({
    required this.sessionId,
    required this.position,
    required this.total,
    required this.questionId,
    required this.questionType,
    required this.availableLanguages,
    required this.languageMode,
    required this.stem,
    required this.options,
    this.elapsedMs = 0,
    this.previousAnswer,
    this.note,
    this.timeRemainingMs,
    this.difficulty,
  });

  factory QuestionDelivery.fromJson(JsonMap json) => QuestionDelivery(
        sessionId: json['session_id'] as String,
        position: json['position'] as int,
        total: json['total'] as int,
        questionId: json['question_id'] as String,
        questionType: json['question_type'] as String,
        availableLanguages: (json['available_languages'] as List? ?? const []).cast<String>(),
        languageMode: (json['language_mode'] as String?) ?? 'en',
        stem: Localized.fromJson(json['stem']),
        options: (json['options'] as List? ?? const [])
            .map((e) => OptionDelivery.fromJson(e as JsonMap))
            .toList(),
        elapsedMs: json['elapsed_ms'] as int? ?? 0,
        previousAnswer: json['previous_answer'] == null
            ? null
            : PreviousAnswer.fromJson(json['previous_answer'] as JsonMap),
        note: json['note'] as String?,
        timeRemainingMs: json['time_remaining_ms'] as int?,
        difficulty: json['difficulty'] as int?,
      );
}

class PerOptionExplanation {
  final int orderIndex;
  final bool isCorrect;
  final Localized explanation;
  const PerOptionExplanation({
    required this.orderIndex,
    required this.isCorrect,
    required this.explanation,
  });
  factory PerOptionExplanation.fromJson(JsonMap json) => PerOptionExplanation(
        orderIndex: json['order_index'] as int,
        isCorrect: json['is_correct'] as bool,
        explanation: Localized.fromJson(json['explanation']),
      );
}

class AnswerResult {
  final bool isCorrect;
  final List<int> correctIndexes;
  final List<int> selectedIndexes;
  final Localized correctRationale;
  final Localized keyPointSummary;
  final List<PerOptionExplanation> perOption;
  final JsonMap mapping;
  final List<JsonMap> history;

  const AnswerResult({
    required this.isCorrect,
    required this.correctIndexes,
    required this.selectedIndexes,
    required this.correctRationale,
    required this.keyPointSummary,
    required this.perOption,
    this.mapping = const {},
    this.history = const [],
  });

  factory AnswerResult.fromJson(JsonMap json) => AnswerResult(
        isCorrect: json['is_correct'] as bool,
        correctIndexes: (json['correct_indexes'] as List).cast<int>(),
        selectedIndexes: (json['selected_indexes'] as List).cast<int>(),
        correctRationale: Localized.fromJson(json['correct_rationale']),
        keyPointSummary: Localized.fromJson(json['key_point_summary']),
        perOption: (json['per_option'] as List? ?? const [])
            .map((e) => PerOptionExplanation.fromJson(e as JsonMap))
            .toList(),
        mapping: (json['mapping'] as JsonMap?) ?? const {},
        history: (json['history'] as List? ?? const []).cast<JsonMap>(),
      );
}

class DomainBreakdown {
  final String? domainId;
  final String? domainName;
  final int answered;
  final int correct;
  const DomainBreakdown({
    this.domainId,
    this.domainName,
    required this.answered,
    required this.correct,
  });
  factory DomainBreakdown.fromJson(JsonMap json) => DomainBreakdown(
        domainId: json['domain_id'] as String?,
        domainName: json['domain_name'] as String?,
        answered: json['answered'] as int,
        correct: json['correct'] as int,
      );
  double get accuracy => answered == 0 ? 0 : correct / answered;
}

class WrongQuestion {
  final String questionId;
  final Localized stem;
  final List<int> selectedIndexes;
  final List<int> correctIndexes;
  const WrongQuestion({
    required this.questionId,
    required this.stem,
    required this.selectedIndexes,
    required this.correctIndexes,
  });
  factory WrongQuestion.fromJson(JsonMap json) => WrongQuestion(
        questionId: json['question_id'] as String,
        stem: Localized.fromJson(json['stem']),
        selectedIndexes: (json['selected_indexes'] as List).cast<int>(),
        correctIndexes: (json['correct_indexes'] as List).cast<int>(),
      );
}

class SessionSummary {
  final String sessionId;
  final int totalQuestions;
  final int answeredCount;
  final int correctCount;
  final double accuracy;
  final int totalTimeSpentMs;
  final List<DomainBreakdown> domains;
  final List<WrongQuestion> wrongQuestions;
  const SessionSummary({
    required this.sessionId,
    required this.totalQuestions,
    required this.answeredCount,
    required this.correctCount,
    required this.accuracy,
    required this.totalTimeSpentMs,
    required this.domains,
    required this.wrongQuestions,
  });
  factory SessionSummary.fromJson(JsonMap json) => SessionSummary(
        sessionId: json['session_id'] as String,
        totalQuestions: json['total_questions'] as int,
        answeredCount: json['answered_count'] as int,
        correctCount: json['correct_count'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
        totalTimeSpentMs: json['total_time_spent_ms'] as int,
        domains: (json['domains'] as List? ?? const [])
            .map((e) => DomainBreakdown.fromJson(e as JsonMap))
            .toList(),
        wrongQuestions: (json['wrong_questions'] as List? ?? const [])
            .map((e) => WrongQuestion.fromJson(e as JsonMap))
            .toList(),
      );
}

class QuestionState {
  final bool isBookmarked;
  final bool isFlaggedReview;
  final bool isMastered;
  final bool isQuestioned;
  final String? note;
  final String? errorType;
  const QuestionState({
    this.isBookmarked = false,
    this.isFlaggedReview = false,
    this.isMastered = false,
    this.isQuestioned = false,
    this.note,
    this.errorType,
  });
  factory QuestionState.fromJson(JsonMap json) => QuestionState(
        isBookmarked: json['is_bookmarked'] as bool? ?? false,
        isFlaggedReview: json['is_flagged_review'] as bool? ?? false,
        isMastered: json['is_mastered'] as bool? ?? false,
        isQuestioned: json['is_questioned'] as bool? ?? false,
        note: json['note'] as String?,
        errorType: json['error_type'] as String?,
      );
}

class RelatedQuestion {
  final String questionId;
  final Localized stem;
  final String? knowledgePointId;
  const RelatedQuestion({
    required this.questionId,
    required this.stem,
    this.knowledgePointId,
  });
  factory RelatedQuestion.fromJson(JsonMap json) => RelatedQuestion(
        questionId: json['question_id'] as String,
        stem: Localized.fromJson(json['stem']),
        knowledgePointId: json['knowledge_point_id'] as String?,
      );
}

class DashboardOut {
  final int practicedQuestions;
  final int totalAnswered;
  final int correctCount;
  final double accuracy;
  final int studyTimeMs;
  final int streakDays;
  final String? lastActiveAt;
  const DashboardOut({
    required this.practicedQuestions,
    required this.totalAnswered,
    required this.correctCount,
    required this.accuracy,
    required this.studyTimeMs,
    required this.streakDays,
    this.lastActiveAt,
  });
  factory DashboardOut.fromJson(JsonMap json) => DashboardOut(
        practicedQuestions: json['practiced_questions'] as int,
        totalAnswered: json['total_answered'] as int,
        correctCount: json['correct_count'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
        studyTimeMs: json['study_time_ms'] as int,
        streakDays: json['streak_days'] as int,
        lastActiveAt: json['last_active_at'] as String?,
      );
}

class DomainMastery {
  final String domainId;
  final int number;
  final String name;
  final double weightPct;
  final int answered;
  final int correct;
  final double accuracy;
  final int avgTimeMs;
  final String masteryLevel;
  const DomainMastery({
    required this.domainId,
    required this.number,
    required this.name,
    required this.weightPct,
    required this.answered,
    required this.correct,
    required this.accuracy,
    required this.avgTimeMs,
    required this.masteryLevel,
  });
  factory DomainMastery.fromJson(JsonMap json) => DomainMastery(
        domainId: json['domain_id'] as String,
        number: json['number'] as int,
        name: json['name'] as String,
        weightPct: (json['weight_pct'] as num).toDouble(),
        answered: json['answered'] as int,
        correct: json['correct'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
        avgTimeMs: json['avg_time_ms'] as int,
        masteryLevel: json['mastery_level'] as String,
      );
}

class TrendPoint {
  final String date;
  final int answered;
  final int correct;
  final double accuracy;
  const TrendPoint({
    required this.date,
    required this.answered,
    required this.correct,
    required this.accuracy,
  });
  factory TrendPoint.fromJson(JsonMap json) => TrendPoint(
        date: json['date'] as String,
        answered: json['answered'] as int,
        correct: json['correct'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
      );
}

class TrendOut {
  final int windowDays;
  final List<TrendPoint> points;
  const TrendOut({required this.windowDays, required this.points});
  factory TrendOut.fromJson(JsonMap json) => TrendOut(
        windowDays: json['window_days'] as int,
        points: (json['points'] as List? ?? const [])
            .map((e) => TrendPoint.fromJson(e as JsonMap))
            .toList(),
      );
}

class WeakArea {
  final String? domainId;
  final String? knowledgePointId;
  final String label;
  final int answered;
  final int correct;
  final double accuracy;
  const WeakArea({
    this.domainId,
    this.knowledgePointId,
    required this.label,
    required this.answered,
    required this.correct,
    required this.accuracy,
  });
  factory WeakArea.fromJson(JsonMap json) => WeakArea(
        domainId: json['domain_id'] as String?,
        knowledgePointId: json['knowledge_point_id'] as String?,
        label: json['label'] as String,
        answered: json['answered'] as int,
        correct: json['correct'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
      );
}

class WeakAreasOut {
  final List<WeakArea> weakDomains;
  final List<WeakArea> weakKnowledgePoints;
  const WeakAreasOut({required this.weakDomains, required this.weakKnowledgePoints});
  factory WeakAreasOut.fromJson(JsonMap json) => WeakAreasOut(
        weakDomains: (json['weak_domains'] as List? ?? const [])
            .map((e) => WeakArea.fromJson(e as JsonMap))
            .toList(),
        weakKnowledgePoints: (json['weak_knowledge_points'] as List? ?? const [])
            .map((e) => WeakArea.fromJson(e as JsonMap))
            .toList(),
      );
}

class ErrorTypeBreakdown {
  final String? errorType;
  final int count;
  const ErrorTypeBreakdown({this.errorType, required this.count});
  factory ErrorTypeBreakdown.fromJson(JsonMap json) => ErrorTypeBreakdown(
        errorType: json['error_type'] as String?,
        count: json['count'] as int,
      );
}

class ErrorTypeOut {
  final int totalWrongClassified;
  final List<ErrorTypeBreakdown> distribution;
  const ErrorTypeOut({required this.totalWrongClassified, required this.distribution});
  factory ErrorTypeOut.fromJson(JsonMap json) => ErrorTypeOut(
        totalWrongClassified: json['total_wrong_classified'] as int,
        distribution: (json['distribution'] as List? ?? const [])
            .map((e) => ErrorTypeBreakdown.fromJson(e as JsonMap))
            .toList(),
      );
}

class ReviewRecommendation {
  final WeakArea? focusDomain;
  final List<String> wrongToReview;
  final List<String> nextPracticeQuestionIds;
  final String rationale;
  const ReviewRecommendation({
    this.focusDomain,
    required this.wrongToReview,
    required this.nextPracticeQuestionIds,
    required this.rationale,
  });
  factory ReviewRecommendation.fromJson(JsonMap json) => ReviewRecommendation(
        focusDomain: json['focus_domain'] == null
            ? null
            : WeakArea.fromJson(json['focus_domain'] as JsonMap),
        wrongToReview: (json['wrong_to_review'] as List? ?? const []).cast<String>(),
        nextPracticeQuestionIds:
            (json['next_practice_question_ids'] as List? ?? const []).cast<String>(),
        rationale: json['rationale'] as String? ?? '',
      );
}

class ExamSession {
  final String id;
  final String status;
  final String sessionKind;
  final int totalQuestions;
  final int correctCount;
  final String startedAt;
  final String? endedAt;
  final int? timeRemainingMs;
  final JsonMap config;
  const ExamSession({
    required this.id,
    required this.status,
    required this.sessionKind,
    required this.totalQuestions,
    required this.correctCount,
    required this.startedAt,
    this.endedAt,
    this.timeRemainingMs,
    this.config = const {},
  });
  factory ExamSession.fromJson(JsonMap json) => ExamSession(
        id: json['id'] as String,
        status: json['status'] as String,
        sessionKind: json['session_kind'] as String,
        totalQuestions: json['total_questions'] as int,
        correctCount: json['correct_count'] as int,
        startedAt: json['started_at'] as String,
        endedAt: json['ended_at'] as String?,
        timeRemainingMs: json['time_remaining_ms'] as int?,
        config: (json['config'] as JsonMap?) ?? const {},
      );
  bool get isCat => sessionKind == 'cat';
  bool get isInProgress => status == 'in_progress';
}

class ExamAnswerAck {
  final int position;
  final bool saved;
  final int timeRemainingMs;
  final bool finished;
  const ExamAnswerAck({
    required this.position,
    required this.saved,
    required this.timeRemainingMs,
    this.finished = false,
  });
  factory ExamAnswerAck.fromJson(JsonMap json) => ExamAnswerAck(
        position: json['position'] as int,
        saved: json['saved'] as bool,
        timeRemainingMs: json['time_remaining_ms'] as int,
        finished: json['finished'] as bool? ?? false,
      );
}

class DomainPerformance {
  final String? domainId;
  final String? domainName;
  final double? weightPct;
  final int answered;
  final int correct;
  final double accuracy;
  const DomainPerformance({
    this.domainId,
    this.domainName,
    this.weightPct,
    required this.answered,
    required this.correct,
    required this.accuracy,
  });
  factory DomainPerformance.fromJson(JsonMap json) => DomainPerformance(
        domainId: json['domain_id'] as String?,
        domainName: json['domain_name'] as String?,
        weightPct: (json['weight_pct'] as num?)?.toDouble(),
        answered: json['answered'] as int,
        correct: json['correct'] as int,
        accuracy: (json['accuracy'] as num).toDouble(),
      );
}

class ExamReport {
  final String sessionId;
  final String status;
  final int totalQuestions;
  final int answeredCount;
  final int correctCount;
  final double scaledScore;
  final double maxScore;
  final double passingScore;
  final bool passed;
  final double accuracy;
  final int totalTimeMs;
  final int avgTimeMs;
  final List<DomainPerformance> domains;
  final List<WrongQuestion> wrongQuestions;
  final double? abilityEstimate;
  final double? abilityCiLower;
  final double? abilityCiUpper;
  final double? sem;
  final String? readinessLevel;
  final String? disclaimer;

  const ExamReport({
    required this.sessionId,
    required this.status,
    required this.totalQuestions,
    required this.answeredCount,
    required this.correctCount,
    required this.scaledScore,
    required this.maxScore,
    required this.passingScore,
    required this.passed,
    required this.accuracy,
    required this.totalTimeMs,
    required this.avgTimeMs,
    required this.domains,
    required this.wrongQuestions,
    this.abilityEstimate,
    this.abilityCiLower,
    this.abilityCiUpper,
    this.sem,
    this.readinessLevel,
    this.disclaimer,
  });

  factory ExamReport.fromJson(JsonMap json) => ExamReport(
        sessionId: json['session_id'] as String,
        status: json['status'] as String,
        totalQuestions: json['total_questions'] as int,
        answeredCount: json['answered_count'] as int,
        correctCount: json['correct_count'] as int,
        scaledScore: (json['scaled_score'] as num).toDouble(),
        maxScore: (json['max_score'] as num).toDouble(),
        passingScore: (json['passing_score'] as num).toDouble(),
        passed: json['passed'] as bool,
        accuracy: (json['accuracy'] as num).toDouble(),
        totalTimeMs: json['total_time_ms'] as int,
        avgTimeMs: json['avg_time_ms'] as int,
        domains: (json['domains'] as List? ?? const [])
            .map((e) => DomainPerformance.fromJson(e as JsonMap))
            .toList(),
        wrongQuestions: (json['wrong_questions'] as List? ?? const [])
            .map((e) => WrongQuestion.fromJson(e as JsonMap))
            .toList(),
        abilityEstimate: (json['ability_estimate'] as num?)?.toDouble(),
        abilityCiLower: (json['ability_ci_lower'] as num?)?.toDouble(),
        abilityCiUpper: (json['ability_ci_upper'] as num?)?.toDouble(),
        sem: (json['sem'] as num?)?.toDouble(),
        readinessLevel: json['readiness_level'] as String?,
        disclaimer: json['disclaimer'] as String?,
      );
}

class ReviewOption {
  final int orderIndex;
  final Localized content;
  final bool isCorrect;
  final Localized explanation;
  const ReviewOption({
    required this.orderIndex,
    required this.content,
    required this.isCorrect,
    required this.explanation,
  });
  factory ReviewOption.fromJson(JsonMap json) => ReviewOption(
        orderIndex: json['order_index'] as int,
        content: Localized.fromJson(json['content']),
        isCorrect: json['is_correct'] as bool,
        explanation: Localized.fromJson(json['explanation']),
      );
}

class ReviewItem {
  final int position;
  final String questionId;
  final String questionType;
  final List<String> availableLanguages;
  final Localized stem;
  final List<ReviewOption> options;
  final Localized correctRationale;
  final Localized keyPointSummary;
  final List<int>? yourSelected;
  final int? timeSpentMs;
  const ReviewItem({
    required this.position,
    required this.questionId,
    required this.questionType,
    required this.availableLanguages,
    required this.stem,
    required this.options,
    required this.correctRationale,
    required this.keyPointSummary,
    this.yourSelected,
    this.timeSpentMs,
  });
  factory ReviewItem.fromJson(JsonMap json) {
    final ya = json['your_answer'] as JsonMap?;
    return ReviewItem(
      position: json['position'] as int,
      questionId: json['question_id'] as String,
      questionType: json['question_type'] as String,
      availableLanguages: (json['available_languages'] as List? ?? const []).cast<String>(),
      stem: Localized.fromJson(json['stem']),
      options: (json['options'] as List? ?? const [])
          .map((e) => ReviewOption.fromJson(e as JsonMap))
          .toList(),
      correctRationale: Localized.fromJson(json['correct_rationale']),
      keyPointSummary: Localized.fromJson(json['key_point_summary']),
      yourSelected: ya == null ? null : (ya['selected'] as List).cast<int>(),
      timeSpentMs: json['time_spent_ms'] as int?,
    );
  }
}

class ExamHistoryItem {
  final String id;
  final String startedAt;
  final String? endedAt;
  final String status;
  final int totalQuestions;
  final int correctCount;
  final double scaledScore;
  final double maxScore;
  final bool passed;
  final double accuracy;
  const ExamHistoryItem({
    required this.id,
    required this.startedAt,
    this.endedAt,
    required this.status,
    required this.totalQuestions,
    required this.correctCount,
    required this.scaledScore,
    required this.maxScore,
    required this.passed,
    required this.accuracy,
  });
  factory ExamHistoryItem.fromJson(JsonMap json) => ExamHistoryItem(
        id: json['id'] as String,
        startedAt: json['started_at'] as String,
        endedAt: json['ended_at'] as String?,
        status: json['status'] as String,
        totalQuestions: json['total_questions'] as int,
        correctCount: json['correct_count'] as int,
        scaledScore: (json['scaled_score'] as num).toDouble(),
        maxScore: (json['max_score'] as num).toDouble(),
        passed: json['passed'] as bool,
        accuracy: (json['accuracy'] as num).toDouble(),
      );
}
