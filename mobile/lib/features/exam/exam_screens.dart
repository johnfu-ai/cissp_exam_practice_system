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
import 'package:cissp_compass/features/exam/cat_runner_state.dart';
import 'package:cissp_compass/features/exam/format.dart';
import 'package:cissp_compass/features/practice/runner_machine.dart';
import 'package:cissp_compass/features/shared/option_list.dart';

const _langModes = ['en', 'zh', 'bilingual'];

class ExamHomeScreen extends ConsumerStatefulWidget {
  const ExamHomeScreen({super.key});

  @override
  ConsumerState<ExamHomeScreen> createState() => _ExamHomeScreenState();
}

class _ExamHomeScreenState extends ConsumerState<ExamHomeScreen> {
  String _languageMode = 'en';
  bool _ackFixed = false;
  bool _ackCat = false;
  bool _startingFixed = false;
  bool _startingCat = false;
  List<ExamSession> _resume = const [];
  List<ExamHistoryItem> _history = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final userMode = ref.read(authSessionProvider).user?.languageMode;
    if (userMode != null) _languageMode = userMode;
    final api = ref.read(cisspApiProvider);
    final prefs = ref.read(prefsStoreProvider);
    await _refreshResume(api, prefs);
    try {
      final hist = await api.examHistory();
      if (mounted) setState(() => _history = hist);
    } catch (e, s) {
      logError(e, s, 'exam:history');
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _refreshResume(CisspApi api, PrefsStore prefs) async {
    var ids = await prefs.getExamSessionIds();
    final active = <ExamSession>[];
    var changed = false;
    for (final id in List<String>.from(ids)) {
      try {
        final s = await api.getExam(id);
        if (s.isInProgress) {
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
        logError(e, s, 'exam:refreshResume');
      }
    }
    if (changed) await prefs.setExamSessionIds(ids);
    if (mounted) setState(() => _resume = active);
  }

  Future<void> _trackAndGo(String id) async {
    final prefs = ref.read(prefsStoreProvider);
    final ids = await prefs.getExamSessionIds();
    await prefs.setExamSessionIds(trackSessionId(ids, id));
    if (mounted) context.go('/exam/sessions/$id');
  }

  Future<void> _start(String kind) async {
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      if (kind == 'cat') {
        _startingCat = true;
      } else {
        _startingFixed = true;
      }
    });
    try {
      final session = await ref.read(cisspApiProvider).createExam({
        'kind': kind,
        'language_mode': _languageMode,
      });
      await _trackAndGo(session.id);
    } catch (e, s) {
      logError(e, s, 'exam:create');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.examCouldNotStart)),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _startingFixed = false;
          _startingCat = false;
        });
      }
    }
  }

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
        Text(l10n.examTitle, style: theme.textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(l10n.examDescription),
        if (_loading)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Text(l10n.examLoading),
          )
        else ...[
          if (_resume.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(l10n.examActiveSessions, style: theme.textTheme.titleMedium),
            for (final s in _resume)
              Card(
                child: ListTile(
                  title: Text(
                    s.isCat ? l10n.examCatTitle : l10n.examFixedTitle,
                  ),
                  subtitle: Text(l10n.examResume),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.go('/exam/sessions/${s.id}'),
                ),
              ),
          ],
          const SizedBox(height: 16),
          Text(l10n.practiceLanguage, style: theme.textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _languageMode,
            items: [
              for (final m in _langModes)
                DropdownMenuItem(value: m, child: Text(_langLabel(l10n, m))),
            ],
            onChanged: (v) => setState(() => _languageMode = v ?? 'en'),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.examFixedTitle, style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _ackFixed,
                    onChanged: (v) => setState(() => _ackFixed = v ?? false),
                    title: Text(l10n.examAcknowledgeFixed),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  FilledButton(
                    onPressed: !_ackFixed || _startingFixed
                        ? null
                        : () => _start('fixed'),
                    child: Text(
                      _startingFixed ? l10n.examLoading : l10n.examStartFixed,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.examCatTitle, style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(
                    l10n.examCatDisclaimer,
                    style: const TextStyle(color: AppColors.muted),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _ackCat,
                    onChanged: (v) => setState(() => _ackCat = v ?? false),
                    title: Text(l10n.examAcknowledgeCat),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  FilledButton(
                    onPressed:
                        !_ackCat || _startingCat ? null : () => _start('cat'),
                    child: Text(
                      _startingCat ? l10n.examLoading : l10n.examStartCat,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_history.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(l10n.examHistory, style: theme.textTheme.titleMedium),
            for (final h in _history)
              Card(
                child: ListTile(
                  title: Text(
                    '${h.passed ? l10n.examPass : l10n.examFail} · ${h.scaledScore.round()}',
                  ),
                  subtitle: Text(
                    '${fmtPct(h.accuracy)} · ${h.startedAt}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () =>
                      context.go('/exam/sessions/${h.id}/report'),
                ),
              ),
          ],
        ],
        const LegalFooter(),
      ],
    );
  }
}

class ExamRunnerScreen extends ConsumerStatefulWidget {
  const ExamRunnerScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  ConsumerState<ExamRunnerScreen> createState() => _ExamRunnerScreenState();
}

class _ExamRunnerScreenState extends ConsumerState<ExamRunnerScreen> {
  ExamSession? _session;
  bool _loading = true;
  String? _error;

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
      final s = await ref.read(cisspApiProvider).getExam(widget.sessionId);
      if (!s.isInProgress) {
        await _untrack();
        if (mounted) {
          context.go('/exam/sessions/${widget.sessionId}/report');
        }
        return;
      }
      if (mounted) setState(() => _session = s);
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 404 || err.status == 409) {
        await _untrack();
        if (mounted) {
          context.go('/exam/sessions/${widget.sessionId}/report');
        }
        return;
      }
      if (mounted) setState(() => _error = err.message);
    } catch (e, s) {
      logError(e, s, 'exam:loadSession');
      if (mounted) {
        setState(() => _error = AppLocalizations.of(context)!.commonErrorTitle);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _untrack() async {
    final prefs = ref.read(prefsStoreProvider);
    final ids = await prefs.getExamSessionIds();
    await prefs.setExamSessionIds(untrackSessionId(ids, widget.sessionId));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.examTitle)),
        body: Center(child: Text(l10n.examLoading)),
      );
    }
    if (_error != null || _session == null) {
      return Scaffold(
        appBar: AppBar(
          title: Text(l10n.examTitle),
          leading: IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => context.go('/exam'),
          ),
        ),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? l10n.commonErrorTitle),
              FilledButton(onPressed: _load, child: Text(l10n.commonRetry)),
            ],
          ),
        ),
      );
    }
    final session = _session!;
    if (session.isCat) {
      return _CatExamBody(sessionId: widget.sessionId, session: session);
    }
    return _FixedExamBody(sessionId: widget.sessionId, session: session);
  }
}

Future<void> _untrackExam(WidgetRef ref, String sessionId) async {
  final prefs = ref.read(prefsStoreProvider);
  final ids = await prefs.getExamSessionIds();
  await prefs.setExamSessionIds(untrackSessionId(ids, sessionId));
}

class _FixedExamBody extends ConsumerStatefulWidget {
  const _FixedExamBody({required this.sessionId, required this.session});
  final String sessionId;
  final ExamSession session;

  @override
  ConsumerState<_FixedExamBody> createState() => _FixedExamBodyState();
}

class _FixedExamBodyState extends ConsumerState<_FixedExamBody> {
  int _position = 0;
  QuestionDelivery? _delivery;
  final Map<int, List<int>> _selections = {};
  final Set<int> _answered = {};
  String _languageMode = 'en';
  String _startedAt = '';
  bool _loadingQ = true;
  bool _busy = false;
  int _remainingMs = 0;
  DateTime? _deadline;
  Timer? _tick;
  bool _finishing = false;

  ExamSession get _session => widget.session;

  @override
  void initState() {
    super.initState();
    _remainingMs = _session.timeRemainingMs ?? 0;
    if (_session.timeRemainingMs != null) {
      _deadline = DateTime.now().add(Duration(milliseconds: _session.timeRemainingMs!));
    }
    _tick = Timer.periodic(const Duration(seconds: 1), (_) => _onTick());
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadQuestion(0));
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  void _onTick() {
    if (_deadline == null || _finishing) return;
    final ms = _deadline!.difference(DateTime.now()).inMilliseconds;
    if (!mounted) return;
    setState(() => _remainingMs = ms < 0 ? 0 : ms);
    if (ms <= 0) {
      _finishing = true;
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.examTimeUp)),
      );
      _finish();
    }
  }

  Future<void> _loadQuestion(int position) async {
    setState(() {
      _loadingQ = true;
      _position = position;
    });
    try {
      final q = await ref
          .read(cisspApiProvider)
          .examQuestion(widget.sessionId, position);
      if (!mounted) return;
      setState(() {
        _delivery = q;
        _languageMode = q.languageMode;
        _startedAt = DateTime.now().toUtc().toIso8601String();
        _selections.putIfAbsent(
          position,
          () => List<int>.from(q.previousAnswer?.selected ?? const []),
        );
        if (q.previousAnswer != null) _answered.add(position);
        if (q.timeRemainingMs != null) {
          _remainingMs = q.timeRemainingMs!;
          _deadline =
              DateTime.now().add(Duration(milliseconds: q.timeRemainingMs!));
        }
        _loadingQ = false;
      });
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) {
        await _goReport();
        return;
      }
      if (mounted) setState(() => _loadingQ = false);
    } catch (e, s) {
      logError(e, s, 'exam:next');
      if (mounted) setState(() => _loadingQ = false);
    }
  }

  Future<void> _upsertCurrent() async {
    final delivery = _delivery;
    final selected = _selections[_position] ?? const <int>[];
    if (delivery == null || selected.isEmpty) return;
    try {
      final ack = await ref.read(cisspApiProvider).submitExamAnswer(
        widget.sessionId,
        {
          'position': _position,
          'selected': selected,
          'started_at': _startedAt,
        },
      );
      if (ack.finished) {
        await _goReport();
        return;
      }
      setState(() {
        _answered.add(_position);
        _remainingMs = ack.timeRemainingMs;
        _deadline =
            DateTime.now().add(Duration(milliseconds: ack.timeRemainingMs));
      });
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) await _goReport();
    }
  }

  Future<void> _goTo(int position) async {
    if (_busy || position < 0 || position >= _session.totalQuestions) return;
    setState(() => _busy = true);
    await _upsertCurrent();
    if (!mounted) return;
    await _loadQuestion(position);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _finish() async {
    if (_busy && _finishing) {
      // allow time-up finish even if busy flag set elsewhere
    }
    setState(() => _busy = true);
    try {
      await _upsertCurrent();
      await ref.read(cisspApiProvider).finishExam(widget.sessionId);
      await _goReport();
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) {
        await _goReport();
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err.message)),
        );
        setState(() => _busy = false);
      }
    } catch (e, s) {
      logError(e, s, 'exam:upsert');
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _goReport() async {
    await _untrackExam(ref, widget.sessionId);
    if (mounted) {
      context.go('/exam/sessions/${widget.sessionId}/report');
    }
  }

  void _toggle(int orderIndex) {
    final delivery = _delivery;
    if (delivery == null) return;
    final cur = List<int>.from(_selections[_position] ?? const []);
    final next = toggleSelection(
      RunnerState(phase: RunnerPhase.selecting, selected: cur),
      orderIndex,
      delivery.questionType,
    ).selected;
    setState(() => _selections[_position] = next);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final delivery = _delivery;
    final selected = _selections[_position] ?? const <int>[];
    final critical = isTimeCritical(_remainingMs);

    final scaffold = Scaffold(
      appBar: AppBar(
        title: Text(
          delivery == null
              ? l10n.examTitle
              : l10n.examQuestionOf(delivery.position + 1, delivery.total),
        ),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/exam'),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text(
                fmtCountdown(_remainingMs),
                style: TextStyle(
                  color: critical ? AppColors.destructive : null,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
      body: _loadingQ || delivery == null
          ? Center(child: Text(l10n.examLoading))
          : Column(
              children: [
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
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
                          setState(() => _languageMode = s.first);
                        },
                      ),
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
                        selectedIndexes: selected,
                        questionType: delivery.questionType,
                        languageMode: _languageMode,
                        onToggle: _toggle,
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (var i = 0; i < _session.totalQuestions; i++)
                            ActionChip(
                              label: Text('${i + 1}'),
                              backgroundColor: i == _position
                                  ? AppColors.primary.withValues(alpha: 0.15)
                                  : _answered.contains(i)
                                      ? AppColors.success.withValues(alpha: 0.12)
                                      : null,
                              onPressed: _busy ? null : () => _goTo(i),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        OutlinedButton(
                          onPressed: _position == 0 || _busy
                              ? null
                              : () => _goTo(_position - 1),
                          child: Text(l10n.commonPrevious),
                        ),
                        const SizedBox(width: 8),
                        if (_position + 1 < _session.totalQuestions)
                          Expanded(
                            child: FilledButton(
                              onPressed:
                                  _busy ? null : () => _goTo(_position + 1),
                              child: Text(l10n.commonNext),
                            ),
                          )
                        else
                          Expanded(
                            child: FilledButton(
                              onPressed: _busy ? null : _finish,
                              child: Text(l10n.examFinish),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );

    return RunnerShortcuts(
      enabled: useDesktopShortcuts(context),
      onSelectSlot: (slot) {
        final opts = delivery?.options;
        if (opts == null || slot < 0 || slot >= opts.length) return;
        _toggle(opts[slot].orderIndex);
      },
      onSubmit: _busy
          ? null
          : () {
              if (_position + 1 < _session.totalQuestions) {
                _goTo(_position + 1);
              } else {
                _finish();
              }
            },
      onPrev: _position == 0 || _busy ? null : () => _goTo(_position - 1),
      onNext: _busy || _position + 1 >= _session.totalQuestions
          ? null
          : () => _goTo(_position + 1),
      child: scaffold,
    );
  }
}

class _CatExamBody extends ConsumerStatefulWidget {
  const _CatExamBody({required this.sessionId, required this.session});
  final String sessionId;
  final ExamSession session;

  @override
  ConsumerState<_CatExamBody> createState() => _CatExamBodyState();
}

class _CatExamBodyState extends ConsumerState<_CatExamBody> {
  QuestionDelivery? _delivery;
  List<int> _selected = const [];
  CatRunnerState _cat = const CatRunnerState(
    languageMode: 'en',
    position: 0,
    questionId: '',
  );
  String _startedAt = '';
  bool _loading = true;
  bool _busy = false;
  int _remainingMs = 0;
  DateTime? _deadline;
  Timer? _tick;
  bool _finishing = false;

  String get _languageMode => _cat.languageMode;

  @override
  void initState() {
    super.initState();
    _remainingMs = widget.session.timeRemainingMs ?? 0;
    if (widget.session.timeRemainingMs != null) {
      _deadline = DateTime.now()
          .add(Duration(milliseconds: widget.session.timeRemainingMs!));
    }
    _tick = Timer.periodic(const Duration(seconds: 1), (_) => _onTick());
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadNext());
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  void _onTick() {
    if (_deadline == null || _finishing) return;
    final ms = _deadline!.difference(DateTime.now()).inMilliseconds;
    if (!mounted) return;
    setState(() => _remainingMs = ms < 0 ? 0 : ms);
    if (ms <= 0) {
      _finishing = true;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.examTimeUp)),
      );
      _finish();
    }
  }

  Future<void> _loadNext() async {
    setState(() => _loading = true);
    try {
      final q = await ref.read(cisspApiProvider).examNext(widget.sessionId);
      if (!mounted) return;
      setState(() {
        _delivery = q;
        _selected = const [];
        _cat = _cat
            .copyWithLanguage(q.languageMode)
            .afterNext(position: q.position, questionId: q.questionId);
        // afterNext increments nextCallCount — correct for real /next loads.
        _startedAt = DateTime.now().toUtc().toIso8601String();
        if (q.timeRemainingMs != null) {
          _remainingMs = q.timeRemainingMs!;
          _deadline =
              DateTime.now().add(Duration(milliseconds: q.timeRemainingMs!));
        }
        _loading = false;
      });
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) {
        await _goReport();
        return;
      }
      if (mounted) setState(() => _loading = false);
    } catch (e, s) {
      logError(e, s, 'exam:finish');
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    final delivery = _delivery;
    if (delivery == null || _selected.isEmpty || _busy) return;
    final l10n = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final ack = await ref.read(cisspApiProvider).submitExamAnswer(
        widget.sessionId,
        {
          'position': delivery.position,
          'selected': _selected,
          'started_at': _startedAt,
        },
      );
      if (ack.finished) {
        await _goReport();
        return;
      }
      await _loadNext();
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409 || err.status == 422) {
        messenger.showSnackBar(
          SnackBar(content: Text(l10n.examNotInProgress)),
        );
        await _goReport();
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _finish() async {
    setState(() => _busy = true);
    try {
      await ref.read(cisspApiProvider).finishExam(widget.sessionId);
      await _goReport();
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      if (err.status == 409) await _goReport();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _goReport() async {
    await _untrackExam(ref, widget.sessionId);
    if (mounted) {
      context.go('/exam/sessions/${widget.sessionId}/report');
    }
  }

  void _toggle(int orderIndex) {
    final delivery = _delivery;
    if (delivery == null) return;
    setState(() {
      _selected = toggleSelection(
        RunnerState(phase: RunnerPhase.selecting, selected: _selected),
        orderIndex,
        delivery.questionType,
      ).selected;
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final delivery = _delivery;
    final critical = isTimeCritical(_remainingMs);

    final scaffold = Scaffold(
      appBar: AppBar(
        title: Text(
          delivery == null
              ? l10n.examCatTitle
              : l10n.examQuestionOf(delivery.position + 1, delivery.total),
        ),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/exam'),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text(
                fmtCountdown(_remainingMs),
                style: TextStyle(
                  color: critical ? AppColors.destructive : null,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
      body: _loading || delivery == null
          ? Center(child: Text(l10n.examLoading))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.warning),
                  ),
                  child: Text(l10n.examCatDisclaimer),
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
                    // CRITICAL: local-only via CatRunnerState — never call examNext.
                    setState(() => _cat = _cat.copyWithLanguage(s.first));
                  },
                ),
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
                  selectedIndexes: _selected,
                  questionType: delivery.questionType,
                  languageMode: _languageMode,
                  onToggle: _toggle,
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _busy || _selected.isEmpty ? null : _submit,
                  child: Text(l10n.commonSubmit),
                ),
              ],
            ),
    );

    return RunnerShortcuts(
      enabled: useDesktopShortcuts(context),
      onSelectSlot: (slot) {
        final opts = delivery?.options;
        if (opts == null || slot < 0 || slot >= opts.length) return;
        _toggle(opts[slot].orderIndex);
      },
      onSubmit:
          _busy || delivery == null || _selected.isEmpty ? null : _submit,
      child: scaffold,
    );
  }
}

class ExamReportScreen extends ConsumerStatefulWidget {
  const ExamReportScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  ConsumerState<ExamReportScreen> createState() => _ExamReportScreenState();
}

class _ExamReportScreenState extends ConsumerState<ExamReportScreen> {
  ExamReport? _report;
  bool _loading = true;
  String? _error;

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
      final r = await ref.read(cisspApiProvider).examReport(widget.sessionId);
      if (mounted) setState(() => _report = r);
    } catch (e, s) {
      logError(e, s, 'exam:report');
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
    final mode = ref.watch(authSessionProvider).user?.languageMode ?? 'en';

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.examReportTitle),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/exam'),
        ),
      ),
      body: _loading
          ? Center(child: Text(l10n.examLoading))
          : _error != null || _report == null
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
                      _report!.passed ? l10n.examPass : l10n.examFail,
                      style: TextStyle(
                        color: _report!.passed
                            ? AppColors.success
                            : AppColors.destructive,
                        fontWeight: FontWeight.w700,
                        fontSize: 28,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${l10n.examScore}: ${_report!.scaledScore.round()} / ${_report!.maxScore.round()}',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    Text(
                      '${l10n.examAccuracy}: ${fmtPct(_report!.accuracy)}',
                    ),
                    Text(fmtDuration(_report!.totalTimeMs)),
                    if (_report!.abilityEstimate != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        '${l10n.examAbility}: ${_report!.abilityEstimate!.toStringAsFixed(2)}'
                        ' (${_report!.abilityCiLower?.toStringAsFixed(2) ?? '—'}'
                        ' – ${_report!.abilityCiUpper?.toStringAsFixed(2) ?? '—'})',
                      ),
                      if (_report!.sem != null)
                        Text('${l10n.examSem}: ${_report!.sem!.toStringAsFixed(3)}'),
                      if (_report!.readinessLevel != null)
                        Text(
                          '${l10n.examReadiness}: ${_report!.readinessLevel}',
                        ),
                      if (_report!.disclaimer != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          _report!.disclaimer!,
                          style: const TextStyle(color: AppColors.muted),
                        ),
                      ],
                    ],
                    if (_report!.domains.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Text(l10n.practiceDomains,
                          style: Theme.of(context).textTheme.titleMedium),
                      for (final d in _report!.domains)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(d.domainName ?? d.domainId ?? '—'),
                          trailing: Text(
                            '${d.correct}/${d.answered} (${fmtPct(d.accuracy)})',
                          ),
                        ),
                    ],
                    if (_report!.wrongQuestions.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(l10n.practiceWrongList,
                          style: Theme.of(context).textTheme.titleMedium),
                      for (final w in _report!.wrongQuestions)
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                BilingualText(text: w.stem, mode: mode),
                                const SizedBox(height: 4),
                                Text(
                                  '${l10n.examYourAnswer}: ${w.selectedIndexes.join(", ")}',
                                ),
                                Text(
                                  '${l10n.examCorrectAnswer}: ${w.correctIndexes.join(", ")}',
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: () => context.go(
                        '/exam/sessions/${widget.sessionId}/review',
                      ),
                      child: Text(l10n.examViewReview),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton(
                      onPressed: () => context.go('/exam'),
                      child: Text(l10n.examBackHome),
                    ),
                    const LegalFooter(),
                  ],
                ),
    );
  }
}

class ExamReviewScreen extends ConsumerStatefulWidget {
  const ExamReviewScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  ConsumerState<ExamReviewScreen> createState() => _ExamReviewScreenState();
}

class _ExamReviewScreenState extends ConsumerState<ExamReviewScreen> {
  List<ReviewItem> _items = const [];
  String _mode = 'en';
  bool _loading = true;
  String? _error;

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
      final api = ref.read(cisspApiProvider);
      final items = await api.examReview(widget.sessionId);
      String mode =
          ref.read(authSessionProvider).user?.languageMode ?? 'en';
      try {
        final session = await api.getExam(widget.sessionId);
        final cfg = session.config['language_mode'];
        if (cfg is String) mode = cfg;
      } catch (e, s) {
        logError(e, s, 'exam:reviewMode');
      }
      if (mounted) {
        setState(() {
          _items = items;
          _mode = mode;
        });
      }
    } catch (e, s) {
      logError(e, s, 'exam:review');
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

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.examReviewTitle),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () =>
              context.go('/exam/sessions/${widget.sessionId}/report'),
        ),
      ),
      body: _loading
          ? Center(child: Text(l10n.examLoading))
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!),
                      FilledButton(
                        onPressed: _load,
                        child: Text(l10n.commonRetry),
                      ),
                    ],
                  ),
                )
              : Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                      child: SegmentedButton<String>(
                        segments: [
                          ButtonSegment(value: 'en', label: Text(l10n.langEn)),
                          ButtonSegment(value: 'zh', label: Text(l10n.langZh)),
                          ButtonSegment(
                            value: 'bilingual',
                            label: Text(l10n.langBilingual),
                          ),
                        ],
                        selected: {_mode},
                        onSelectionChanged: (s) =>
                            setState(() => _mode = s.first),
                      ),
                    ),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _items.length,
                        itemBuilder: (context, i) {
                          final item = _items[i];
                          final correct = item.options
                              .where((o) => o.isCorrect)
                              .map((o) => o.orderIndex)
                              .toList();
                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '#${item.position + 1}',
                                    style:
                                        Theme.of(context).textTheme.labelLarge,
                                  ),
                                  const SizedBox(height: 8),
                                  BilingualText(
                                    text: item.stem,
                                    mode: _mode,
                                    markdown: true,
                                  ),
                                  const SizedBox(height: 8),
                                  for (final o in item.options)
                                    Padding(
                                      padding: const EdgeInsets.only(bottom: 4),
                                      child: Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '${String.fromCharCode(65 + o.orderIndex)}. ',
                                            style: TextStyle(
                                              color: o.isCorrect
                                                  ? AppColors.success
                                                  : AppColors.muted,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          Expanded(
                                            child: BilingualText(
                                              text: o.content,
                                              mode: _mode,
                                              markdown: true,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  const SizedBox(height: 8),
                                  Text(
                                    '${l10n.examYourAnswer}: ${(item.yourSelected ?? const []).join(", ")}',
                                  ),
                                  Text(
                                    '${l10n.examCorrectAnswer}: ${correct.join(", ")}',
                                  ),
                                  const SizedBox(height: 8),
                                  ExplanationPanel(
                                    mode: _mode,
                                    rationale: item.correctRationale,
                                    keyPoints: item.keyPointSummary,
                                    perOption: [
                                      for (final o in item.options)
                                        PerOptionExplanation(
                                          orderIndex: o.orderIndex,
                                          isCorrect: o.isCorrect,
                                          explanation: o.explanation,
                                        ),
                                    ],
                                    keyPointsLabel: l10n.practiceKeyPoints,
                                    optionExplanationsLabel:
                                        l10n.practiceOptionExplanations,
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
    );
  }
}
