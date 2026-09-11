import 'dart:async';

import 'package:cissp_api/cissp_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/crash_reporting.dart';
import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/core/session_tracker.dart';
import 'package:cissp_compass/core/storage.dart';
import 'package:cissp_compass/design/bilingual_text.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/runner_shortcuts.dart';
import 'package:cissp_compass/design/theme.dart';
import 'package:cissp_compass/features/exam/format.dart';
import 'package:cissp_compass/features/practice/answer_metadata.dart';
import 'package:cissp_compass/features/practice/option_shuffle.dart';
import 'package:cissp_compass/features/practice/runner_machine.dart';
import 'package:cissp_compass/features/shared/option_list.dart';

const _counts = [10, 25, 50, 100];
const _subsets = ['all', 'unpracticed', 'wrong', 'bookmarked', 'needs_review'];
const _orders = ['random', 'sequential', 'easy_to_hard', 'weak_first'];
const _langModes = ['en', 'zh', 'bilingual'];
const _questionTypes = ['single_choice', 'multiple_choice', 'true_false'];
const _difficulties = [1, 2, 3, 4, 5];
const _errorTypes = [
  'concept_unclear',
  'misread_stem',
  'memory_lapse',
  'option_confusion',
  'time_pressure',
];

class PracticeHomeScreen extends ConsumerStatefulWidget {
  const PracticeHomeScreen({super.key});

  @override
  ConsumerState<PracticeHomeScreen> createState() => _PracticeHomeScreenState();
}

class _PracticeHomeScreenState extends ConsumerState<PracticeHomeScreen> {
  int _count = 10;
  String _subset = 'all';
  String _orderMode = 'random';
  String? _domainId;
  String? _bookId;
  String? _chapterId;
  String? _languageMode;
  int? _difficulty;
  String? _questionType;
  String? _tagId;
  bool _shuffleOptions = false;
  bool _starting = false;
  String? _error;

  List<DomainOut> _domains = const [];
  List<BookOut> _books = const [];
  List<ChapterOut> _chapters = const [];
  List<TagOut> _tags = const [];
  List<SessionOut> _resume = const [];
  bool _loadingMeta = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final api = ref.read(cisspApiProvider);
    final prefs = ref.read(prefsStoreProvider);
    final userMode = ref.read(authSessionProvider).user?.languageMode;
    setState(() => _languageMode = userMode);

    try {
      final domains = await api.domains();
      List<BookOut> books = const [];
      List<TagOut> tags = const [];
      try {
        books = await api.books();
      } catch (e, s) {
        logError(e, s, 'practice:bootstrap:books');
      }
      try {
        tags = await api.tags();
      } catch (e, s) {
        logError(e, s, 'practice:bootstrap:tags');
      }
      if (mounted) {
        setState(() {
          _domains = domains;
          _books = books;
          _tags = tags;
        });
      }
    } catch (e, s) {
      logError(e, s, 'practice:bootstrap:domains');
    }

    await _refreshResume(api, prefs);
    if (mounted) setState(() => _loadingMeta = false);
  }

  Future<void> _onBookChanged(String? bookId) async {
    setState(() {
      _bookId = bookId;
      _chapterId = null;
      _chapters = const [];
    });
    if (bookId == null) return;
    try {
      final chapters = await ref.read(cisspApiProvider).chapters(bookId);
      if (mounted) setState(() => _chapters = chapters);
    } catch (e, s) {
      logError(e, s, 'practice:chapters');
      if (mounted) setState(() => _chapters = const []);
    }
  }

  Future<void> _refreshResume(CisspApi api, PrefsStore prefs) async {
    var ids = await prefs.getPracticeSessionIds();
    final active = <SessionOut>[];
    var changed = false;
    for (final id in List<String>.from(ids)) {
      try {
        final s = await api.getPractice(id);
        if (s.status == 'in_progress') {
          active.add(s);
        } else {
          ids = untrackSessionId(ids, id);
          changed = true;
        }
      } on DioException catch (e) {
        if (e.response?.statusCode == 404) {
          ids = untrackSessionId(ids, id);
          changed = true;
        }
      } catch (e, s) {
        logError(e, s, 'practice:refreshResume');
      }
    }
    if (changed) await prefs.setPracticeSessionIds(ids);
    if (mounted) setState(() => _resume = active);
  }

  Future<void> _trackAndGo(String id) async {
    final prefs = ref.read(prefsStoreProvider);
    final ids = await prefs.getPracticeSessionIds();
    await prefs.setPracticeSessionIds(trackSessionId(ids, id));
    if (mounted) context.go('/practice/sessions/$id');
  }

  Future<void> _start() async {
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      _starting = true;
      _error = null;
    });
    final api = ref.read(cisspApiProvider);
    final body = <String, dynamic>{
      'count': _count,
      'subset': _subset,
      'order_mode': _orderMode,
      if (_domainId != null) 'domain_id': _domainId,
      if (_bookId != null) 'book_id': _bookId,
      if (_chapterId != null) 'chapter_ids': [_chapterId],
      if (_difficulty != null) 'difficulty': _difficulty,
      if (_questionType != null) 'question_type': _questionType,
      if (_tagId != null) 'tag_id': _tagId,
      if (_languageMode != null) 'language_mode': _languageMode,
      if (_shuffleOptions) 'shuffle_options': true,
    };
    try {
      final session = await api.createPractice(body);
      await _trackAndGo(session.id);
    } catch (e, s) {
      logError(e, s, 'practice:create');
      if (mounted) {
        setState(() {
          _error = l10n.practiceCouldNotStart;
          _starting = false;
        });
      }
    }
  }

  String _subsetLabel(AppLocalizations l10n, String s) => switch (s) {
        'unpracticed' => l10n.subsetUnpracticed,
        'wrong' => l10n.subsetWrong,
        'bookmarked' => l10n.subsetBookmarked,
        'needs_review' => l10n.subsetNeedsReview,
        _ => l10n.subsetAll,
      };

  String _orderLabel(AppLocalizations l10n, String o) => switch (o) {
        'sequential' => l10n.orderSequential,
        'easy_to_hard' => l10n.orderEasyToHard,
        'weak_first' => l10n.orderWeakFirst,
        _ => l10n.orderRandom,
      };

  String _questionTypeLabel(AppLocalizations l10n, String t) => switch (t) {
        'multiple_choice' => l10n.questionTypeMultiple,
        'true_false' => l10n.questionTypeTrueFalse,
        _ => l10n.questionTypeSingle,
      };

  String _langLabel(AppLocalizations l10n, String m) => switch (m) {
        'zh' => l10n.langZh,
        'bilingual' => l10n.langBilingual,
        _ => l10n.langEn,
      };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.practiceTitle, style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(l10n.practiceDescription),
        if (_loadingMeta) ...[
          const SizedBox(height: 24),
          Text(l10n.practiceLoading),
        ] else ...[
          if (_resume.isNotEmpty) ...[
            const SizedBox(height: 20),
            Text(l10n.practiceActiveSessions,
                style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final s in _resume)
              Card(
                child: ListTile(
                  title: Text(l10n.practiceResume),
                  subtitle: Text(
                    '${s.correctCount}/${s.totalQuestions} · ${s.isPaused ? l10n.practiceSessionPaused : ''}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.go('/practice/sessions/${s.id}'),
                ),
              ),
          ],
          const SizedBox(height: 20),
          Text(l10n.practiceNewSession, style: theme.textTheme.titleMedium),
          const SizedBox(height: 12),
          Text(l10n.practiceCount, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final c in _counts)
                ChoiceChip(
                  label: Text('$c'),
                  selected: _count == c,
                  onSelected: (_) => setState(() => _count = c),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceSubset, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _subset,
            items: [
              for (final s in _subsets)
                DropdownMenuItem(value: s, child: Text(_subsetLabel(l10n, s))),
            ],
            onChanged: (v) => setState(() => _subset = v ?? 'all'),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceOrder, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _orderMode,
            items: [
              for (final o in _orders)
                DropdownMenuItem(value: o, child: Text(_orderLabel(l10n, o))),
            ],
            onChanged: (v) => setState(() => _orderMode = v ?? 'random'),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceDomain, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String?>(
            value: _domainId,
            items: [
              DropdownMenuItem<String?>(
                value: null,
                child: Text(l10n.practiceAnyDomain),
              ),
              for (final d in _domains)
                DropdownMenuItem<String?>(
                  value: d.id,
                  child: Text('${d.number}. ${d.name}'),
                ),
            ],
            onChanged: (v) => setState(() => _domainId = v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceBook, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String?>(
            value: _bookId,
            items: [
              DropdownMenuItem<String?>(
                value: null,
                child: Text(l10n.practiceAnyBook),
              ),
              for (final b in _books)
                DropdownMenuItem<String?>(
                  value: b.id,
                  child: Text(b.title),
                ),
            ],
            onChanged: (v) => _onBookChanged(v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceChapter, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String?>(
            value: _chapterId,
            items: [
              DropdownMenuItem<String?>(
                value: null,
                child: Text(l10n.practiceAnyChapter),
              ),
              for (final c in _chapters)
                DropdownMenuItem<String?>(
                  value: c.id,
                  child: Text('${c.orderIndex}. ${c.title}'),
                ),
            ],
            onChanged: _bookId == null
                ? null
                : (v) => setState(() => _chapterId = v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceDifficulty, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<int?>(
            value: _difficulty,
            items: [
              DropdownMenuItem<int?>(
                value: null,
                child: Text(l10n.practiceAnyDifficulty),
              ),
              for (final d in _difficulties)
                DropdownMenuItem<int?>(
                  value: d,
                  child: Text('$d'),
                ),
            ],
            onChanged: (v) => setState(() => _difficulty = v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Text(l10n.practiceQuestionType, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String?>(
            value: _questionType,
            items: [
              DropdownMenuItem<String?>(
                value: null,
                child: Text(l10n.practiceAnyQuestionType),
              ),
              for (final t in _questionTypes)
                DropdownMenuItem<String?>(
                  value: t,
                  child: Text(_questionTypeLabel(l10n, t)),
                ),
            ],
            onChanged: (v) => setState(() => _questionType = v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          if (_tags.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(l10n.practiceTag, style: theme.textTheme.labelLarge),
            const SizedBox(height: 8),
            DropdownButtonFormField<String?>(
              value: _tagId,
              items: [
                DropdownMenuItem<String?>(
                  value: null,
                  child: Text(l10n.practiceAnyTag),
                ),
                for (final t in _tags)
                  DropdownMenuItem<String?>(
                    value: t.id,
                    child: Text(t.name),
                  ),
              ],
              onChanged: (v) => setState(() => _tagId = v),
              decoration: const InputDecoration(border: OutlineInputBorder()),
            ),
          ],
          const SizedBox(height: 16),
          Text(l10n.practiceLanguage, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _languageMode ?? 'en',
            items: [
              for (final m in _langModes)
                DropdownMenuItem(value: m, child: Text(_langLabel(l10n, m))),
            ],
            onChanged: (v) => setState(() => _languageMode = v),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.practiceShuffleOptions),
            value: _shuffleOptions,
            onChanged: (v) => setState(() => _shuffleOptions = v),
          ),
          if (_error != null) ...[
            Text(_error!, style: const TextStyle(color: AppColors.destructive)),
            const SizedBox(height: 8),
          ],
          FilledButton(
            onPressed: _starting ? null : _start,
            child: Text(_starting ? l10n.practiceLoading : l10n.practiceStart),
          ),
        ],
        const LegalFooter(),
      ],
    );
  }
}

class PracticeRunnerScreen extends ConsumerStatefulWidget {
  const PracticeRunnerScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  ConsumerState<PracticeRunnerScreen> createState() =>
      _PracticeRunnerScreenState();
}

class _PracticeRunnerScreenState extends ConsumerState<PracticeRunnerScreen> {
  SessionOut? _session;
  QuestionDelivery? _delivery;
  RunnerState _runner = initialRunnerState(null);
  String _languageMode = 'en';
  int _position = 0;
  String _startedAt = '';
  List<int> _displayOrder = const [];
  bool _loading = true;
  bool _busy = false;
  String? _error;
  bool _bookmarked = false;
  bool _flagged = false;
  bool _mastered = false;
  bool _questioned = false;
  String? _errorType;
  final _noteCtrl = TextEditingController();
  Timer? _tick;
  DateTime _now = DateTime.now();
  List<RelatedQuestion> _related = const [];
  bool _relatedLoading = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadInitial());
  }

  @override
  void dispose() {
    _tick?.cancel();
    _noteCtrl.dispose();
    super.dispose();
  }

  void _ensureTicker() {
    _tick?.cancel();
    final paused = _session?.isPaused ?? true;
    if (paused) return;
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _now = DateTime.now());
    });
  }

  Future<void> _loadInitial() async {
    final api = ref.read(cisspApiProvider);
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final session = await api.getPractice(widget.sessionId);
      if (session.status != 'in_progress') {
        await _untrack();
        if (mounted) {
          context.go('/practice/sessions/${widget.sessionId}/done');
        }
        return;
      }
      final start = await _findFirstUnanswered(api, session.totalQuestions);
      await _loadPosition(api, session, start);
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 404 || err.status == 409) {
        await _untrack();
        if (mounted) context.go('/practice');
        return;
      }
      if (mounted) setState(() => _error = err.message);
    } catch (e, s) {
      logError(e, s, 'practice:loadQuestion');
      if (mounted) setState(() => _error = l10n.commonErrorTitle);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<int> _findFirstUnanswered(CisspApi api, int total) async {
    for (var i = 0; i < total; i++) {
      final q = await api.practiceQuestion(widget.sessionId, i);
      if (q.previousAnswer == null) return i;
    }
    return 0;
  }

  Future<void> _loadPosition(
    CisspApi api,
    SessionOut session,
    int position,
  ) async {
    final delivery = await api.practiceQuestion(widget.sessionId, position);
    final shuffle = session.config['shuffle_options'] == true;
    final order = displayOrderIndexes(
      delivery.options.map((o) => o.orderIndex),
      delivery.questionId,
      shuffle: shuffle,
    );
    if (!mounted) return;
    setState(() {
      _session = session;
      _delivery = delivery;
      _position = position;
      _runner = initialRunnerState(delivery.previousAnswer);
      _languageMode = delivery.languageMode;
      _startedAt = DateTime.now().toUtc().toIso8601String();
      _displayOrder = order;
      _noteCtrl.text = delivery.note ?? '';
      _bookmarked = false;
      _flagged = false;
      _mastered = false;
      _questioned = false;
      _errorType = null;
      _related = const [];
      _relatedLoading = false;
    });
    _ensureTicker();
  }

  Future<void> _untrack() async {
    final prefs = ref.read(prefsStoreProvider);
    final ids = await prefs.getPracticeSessionIds();
    await prefs.setPracticeSessionIds(untrackSessionId(ids, widget.sessionId));
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _submit() async {
    final delivery = _delivery;
    if (delivery == null || !canSubmit(_runner) || _busy) return;
    final l10n = AppLocalizations.of(context)!;
    setState(() => _busy = true);
    try {
      final api = ref.read(cisspApiProvider);
      final result = await api.submitPracticeAnswer(
        widget.sessionId,
        {
          'position': _position,
          'selected': _runner.selected,
          'started_at': _startedAt,
        },
      );
      if (mounted) {
        setState(() => _runner = markSubmitted(_runner, result));
      }
      unawaited(_loadRelated(api, delivery.questionId));
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      _snack(err.status == 409 ? l10n.practiceAlreadyAnswered : err.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadRelated(CisspApi api, String questionId) async {
    if (!mounted) return;
    setState(() => _relatedLoading = true);
    try {
      final related = await api.relatedQuestions(questionId);
      if (mounted) setState(() => _related = related);
    } catch (e, s) {
      logError(e, s, 'practice:related');
      if (mounted) setState(() => _related = const []);
    } finally {
      if (mounted) setState(() => _relatedLoading = false);
    }
  }

  Future<void> _nextOrFinish() async {
    final delivery = _delivery;
    final session = _session;
    if (delivery == null || session == null || _busy) return;
    final l10n = AppLocalizations.of(context)!;
    if (_position + 1 >= delivery.total) {
      setState(() => _busy = true);
      try {
        await ref.read(cisspApiProvider).finishPractice(widget.sessionId);
        await _untrack();
        if (mounted) {
          context.go('/practice/sessions/${widget.sessionId}/done');
        }
      } catch (e, s) {
        logError(e, s, 'practice:finish');
        _snack(l10n.commonErrorTitle);
      } finally {
        if (mounted) setState(() => _busy = false);
      }
      return;
    }
    setState(() => _busy = true);
    try {
      await _loadPosition(
        ref.read(cisspApiProvider),
        session,
        _position + 1,
      );
    } catch (e, s) {
      logError(e, s, 'practice:next');
      _snack(l10n.commonErrorTitle);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pauseResume() async {
    final session = _session;
    if (session == null || _busy) return;
    setState(() => _busy = true);
    try {
      final api = ref.read(cisspApiProvider);
      final next = session.isPaused
          ? await api.resumePractice(widget.sessionId)
          : await api.pausePractice(widget.sessionId);
      if (mounted) {
        setState(() => _session = next);
        _ensureTicker();
      }
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) _snack(err.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _putState(JsonMap body) async {
    final delivery = _delivery;
    if (delivery == null) return;
    try {
      final state = await ref
          .read(cisspApiProvider)
          .putQuestionState(delivery.questionId, body);
      if (!mounted) return;
      setState(() {
        if (body.containsKey('is_bookmarked')) {
          _bookmarked = state.isBookmarked;
        }
        if (body.containsKey('is_flagged_review')) {
          _flagged = state.isFlaggedReview;
        }
        if (body.containsKey('is_mastered')) {
          _mastered = state.isMastered;
        }
        if (body.containsKey('is_questioned')) {
          _questioned = state.isQuestioned;
        }
        if (body.containsKey('note')) {
          _noteCtrl.text = state.note ?? '';
        }
        if (body.containsKey('error_type')) _errorType = state.errorType;
      });
    } catch (e, s) {
      logError(e, s, 'practice:questionState');
      _snack(AppLocalizations.of(context)!.commonErrorTitle);
    }
  }

  String _errorLabel(AppLocalizations l10n, String e) => switch (e) {
        'misread_stem' => l10n.errorMisreadStem,
        'memory_lapse' => l10n.errorMemoryLapse,
        'option_confusion' => l10n.errorOptionConfusion,
        'time_pressure' => l10n.errorTimePressure,
        _ => l10n.errorConceptUnclear,
      };

  String _mappingKindLabel(AppLocalizations l10n, String kind) => switch (kind) {
        'chapter' => l10n.practiceChapter,
        'knowledge_point' => l10n.practiceKeyPoints,
        _ => l10n.practiceDomain,
      };

  List<Widget> _buildAnswerMetadata(
    AppLocalizations l10n,
    AnswerResult result,
  ) {
    final labels = mappingLabelsFrom(result.mapping);
    final history = historyAttemptsFrom(result.history);
    final widgets = <Widget>[];
    if (labels.isNotEmpty) {
      widgets.add(const SizedBox(height: 12));
      widgets.add(
        Text(l10n.practiceMapping, style: Theme.of(context).textTheme.titleSmall),
      );
      widgets.add(const SizedBox(height: 4));
      for (final label in labels) {
        // Taxonomy names stay untranslated (FR-I18N-05).
        widgets.add(
          Text('${_mappingKindLabel(l10n, label.kind)}: ${label.value}'),
        );
      }
    }
    if (history.isNotEmpty) {
      widgets.add(const SizedBox(height: 12));
      widgets.add(
        Text(l10n.practiceHistory, style: Theme.of(context).textTheme.titleSmall),
      );
      widgets.add(const SizedBox(height: 4));
      for (final h in history) {
        final outcome = h.isCorrect
            ? l10n.practiceHistoryCorrect
            : l10n.practiceHistoryIncorrect;
        final when = h.answeredAt == null
            ? ''
            : ' · ${formatRelativePast(h.answeredAt!, _now)}';
        widgets.add(Text('$outcome$when'));
      }
    }
    return widgets;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.practiceTitle)),
        body: Center(child: Text(l10n.practiceLoading)),
      );
    }
    if (_error != null || _delivery == null || _session == null) {
      return Scaffold(
        appBar: AppBar(
          title: Text(l10n.practiceTitle),
          leading: IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => context.go('/practice'),
          ),
        ),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? l10n.commonErrorTitle),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadInitial,
                child: Text(l10n.commonRetry),
              ),
            ],
          ),
        ),
      );
    }

    final delivery = _delivery!;
    final session = _session!;
    final paused = session.isPaused;
    final submitted = _runner.phase == RunnerPhase.submitted;
    final result = _runner.result;
    final started = DateTime.tryParse(session.startedAt);
    final elapsedMs = started == null
        ? delivery.elapsedMs
        : _now.difference(started.toLocal()).inMilliseconds;

    final scaffold = Scaffold(
      appBar: AppBar(
        title: Text(l10n.practiceQuestionOf(delivery.position + 1, delivery.total)),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/practice'),
        ),
        actions: [
          IconButton(
            tooltip: paused ? l10n.practiceResumeAction : l10n.practicePause,
            onPressed: _busy ? null : _pauseResume,
            icon: Icon(paused ? Icons.play_arrow : Icons.pause),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: LinearProgressIndicator(
                  value: delivery.total == 0
                      ? 0
                      : (delivery.position + 1) / delivery.total,
                ),
              ),
              const SizedBox(width: 12),
              Text(fmtCountdown(elapsedMs),
                  style: Theme.of(context).textTheme.labelLarge),
            ],
          ),
          const SizedBox(height: 12),
          SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'en', label: Text(l10n.langEn)),
              ButtonSegment(value: 'zh', label: Text(l10n.langZh)),
              ButtonSegment(
                value: 'bilingual',
                label: Text(l10n.langBilingual),
              ),
            ],
            selected: {_languageMode},
            onSelectionChanged: (s) {
              // Local-only: never refetch / advance.
              setState(() => _languageMode = s.first);
            },
          ),
          if (paused) ...[
            const SizedBox(height: 12),
            Text(
              l10n.practiceSessionPaused,
              style: const TextStyle(color: AppColors.warning),
            ),
          ],
          const SizedBox(height: 16),
          BilingualText(
            text: delivery.stem,
            mode: _languageMode,
            style: Theme.of(context).textTheme.titleMedium,
            markdown: true,
          ),
          const SizedBox(height: 16),
          OptionList(
            options: delivery.options,
            selectedIndexes: _runner.selected,
            questionType: delivery.questionType,
            languageMode: _languageMode,
            displayOrder: _displayOrder,
            result: result,
            enabled: !paused && !submitted,
            onToggle: (oi) {
              setState(() {
                _runner = toggleSelection(_runner, oi, delivery.questionType);
              });
            },
          ),
          if (submitted) ...[
            const SizedBox(height: 12),
            _ResultBanner(
              correct: result?.isCorrect ??
                  delivery.previousAnswer?.isCorrect ??
                  false,
              correctLabel: l10n.practiceCorrect,
              incorrectLabel: l10n.practiceIncorrect,
            ),
            if (result != null) ...[
              const SizedBox(height: 8),
              ExplanationPanel(
                mode: _languageMode,
                rationale: result.correctRationale,
                keyPoints: result.keyPointSummary,
                perOption: result.perOption,
                keyPointsLabel: l10n.practiceKeyPoints,
                optionExplanationsLabel: l10n.practiceOptionExplanations,
              ),
              ..._buildAnswerMetadata(l10n, result),
            ],
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  label: Text(l10n.practiceBookmark),
                  selected: _bookmarked,
                  onSelected: (v) => _putState({'is_bookmarked': v}),
                ),
                FilterChip(
                  label: Text(l10n.practiceFlag),
                  selected: _flagged,
                  onSelected: (v) => _putState({'is_flagged_review': v}),
                ),
                FilterChip(
                  label: Text(l10n.practiceMastered),
                  selected: _mastered,
                  onSelected: (v) => _putState({'is_mastered': v}),
                ),
                FilterChip(
                  label: Text(l10n.practiceQuestioned),
                  selected: _questioned,
                  onSelected: (v) => _putState({'is_questioned': v}),
                ),
              ],
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String?>(
              value: _errorType,
              decoration: InputDecoration(
                labelText: l10n.practiceErrorType,
                border: const OutlineInputBorder(),
              ),
              items: [
                const DropdownMenuItem<String?>(value: null, child: Text('—')),
                for (final e in _errorTypes)
                  DropdownMenuItem(
                    value: e,
                    child: Text(_errorLabel(l10n, e)),
                  ),
              ],
              onChanged: (v) {
                if (v != null) _putState({'error_type': v});
              },
            ),
            const SizedBox(height: 8),
            TextField(
              decoration: InputDecoration(
                labelText: l10n.practiceNote,
                border: const OutlineInputBorder(),
              ),
              controller: _noteCtrl,
              minLines: 1,
              maxLines: 3,
              onSubmitted: (v) => _putState({'note': v}),
              onEditingComplete: () => _putState({'note': _noteCtrl.text}),
            ),
            if (_relatedLoading || _related.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                l10n.practiceRelated,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              if (_relatedLoading)
                Text(l10n.practiceLoading)
              else
                for (final rq in _related)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: BilingualText(
                        text: rq.stem,
                        mode: _languageMode,
                        markdown: true,
                      ),
                    ),
                  ),
            ],
          ],
          const SizedBox(height: 24),
          if (!submitted)
            FilledButton(
              onPressed: paused || _busy || !canSubmit(_runner) ? null : _submit,
              child: Text(l10n.practiceSubmit),
            )
          else
            FilledButton(
              onPressed: _busy ? null : _nextOrFinish,
              child: Text(
                _position + 1 >= delivery.total
                    ? l10n.practiceFinish
                    : l10n.practiceNext,
              ),
            ),
        ],
      ),
    );

    return RunnerShortcuts(
      enabled: useDesktopShortcuts(context),
      onSelectSlot: (slot) {
        if (paused || submitted) return;
        final order = _displayOrder.isEmpty
            ? delivery.options.map((o) => o.orderIndex).toList()
            : _displayOrder;
        if (slot < 0 || slot >= order.length) return;
        setState(() {
          _runner = toggleSelection(_runner, order[slot], delivery.questionType);
        });
      },
      onSubmit: paused || _busy
          ? null
          : () {
              if (!submitted && canSubmit(_runner)) {
                _submit();
              } else if (submitted) {
                _nextOrFinish();
              }
            },
      child: scaffold,
    );
  }
}

class _ResultBanner extends StatelessWidget {
  const _ResultBanner({
    required this.correct,
    required this.correctLabel,
    required this.incorrectLabel,
  });

  final bool correct;
  final String correctLabel;
  final String incorrectLabel;

  @override
  Widget build(BuildContext context) {
    final color = correct ? AppColors.success : AppColors.destructive;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color),
      ),
      child: Row(
        children: [
          Icon(correct ? Icons.check_circle : Icons.cancel, color: color),
          const SizedBox(width: 8),
          Text(
            correct ? correctLabel : incorrectLabel,
            style: TextStyle(color: color, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

class PracticeDoneScreen extends ConsumerStatefulWidget {
  const PracticeDoneScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  ConsumerState<PracticeDoneScreen> createState() => _PracticeDoneScreenState();
}

class _PracticeDoneScreenState extends ConsumerState<PracticeDoneScreen> {
  SessionSummary? _summary;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final s = await ref
          .read(cisspApiProvider)
          .practiceSummary(widget.sessionId);
      if (mounted) setState(() => _summary = s);
    } catch (e, s) {
      logError(e, s, 'practice:summary');
      if (mounted) {
        setState(() => _error = AppLocalizations.of(context)!.commonErrorTitle);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final mode =
        ref.watch(authSessionProvider).user?.languageMode ?? 'en';

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.practiceSummaryTitle),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/practice'),
        ),
      ),
      body: _loading
          ? Center(child: Text(l10n.practiceLoading))
          : _error != null || _summary == null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error ?? l10n.commonErrorTitle),
                      FilledButton(
                        onPressed: _load,
                        child: Text(l10n.commonRetry),
                      ),
                    ],
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(
                      fmtPct(_summary!.accuracy),
                      style: Theme.of(context).textTheme.displaySmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    Text(l10n.practiceAccuracy),
                    const SizedBox(height: 8),
                    Text(
                      '${l10n.practiceTimeSpent}: ${fmtDuration(_summary!.totalTimeSpentMs)}',
                    ),
                    Text(
                      '${_summary!.correctCount}/${_summary!.answeredCount}',
                    ),
                    if (_summary!.domains.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      Text(l10n.practiceDomains,
                          style: Theme.of(context).textTheme.titleMedium),
                      for (final d in _summary!.domains)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(d.domainName ?? d.domainId ?? '—'),
                          trailing: Text(
                            '${d.correct}/${d.answered} (${fmtPct(d.accuracy)})',
                          ),
                        ),
                    ],
                    if (_summary!.wrongQuestions.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(l10n.practiceWrongList,
                          style: Theme.of(context).textTheme.titleMedium),
                      for (final w in _summary!.wrongQuestions)
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: BilingualText(text: w.stem, mode: mode),
                          ),
                        ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: () => context.go('/review'),
                      child: Text(l10n.navReview),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton(
                      onPressed: () => context.go('/practice'),
                      child: Text(l10n.practiceAnother),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: () => context.go('/dashboard'),
                      child: Text(l10n.navHome),
                    ),
                    const LegalFooter(),
                  ],
                ),
    );
  }
}
