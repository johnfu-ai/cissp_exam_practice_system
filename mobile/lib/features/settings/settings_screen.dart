import 'package:cissp_api/cissp_api.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';

import 'package:cissp_compass/core/crash_reporting.dart';
import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';
import 'package:cissp_compass/locale_controller.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _pwdBusy = false;
  String? _pwdMsg;
  String? _pwdErr;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _setInterface(String code) async {
    await ref.read(localeControllerProvider.notifier).setInterfaceLanguage(code);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.settingsSaved)),
      );
    }
  }

  Future<void> _setContentMode(String mode) async {
    final api = ref.read(cisspApiProvider);
    final prefs = ref.read(prefsStoreProvider);
    await prefs.setLanguageMode(mode);
    try {
      await api.putPreferences(languageMode: mode);
      final user = ref.read(authSessionProvider).user;
      if (user != null) {
        await ref.read(authSessionProvider.notifier).setUser(
              copyUser(user, languageMode: mode),
            );
      }
    } catch (e, s) {
      // Local prefs already updated; server sync best-effort.
      logError(e, s, 'settings:syncPreferences');
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.settingsSaved)),
      );
      setState(() {});
    }
  }

  Future<void> _saveGoals({DateTime? examTargetDate, int? dailyGoalAnswers}) async {
    final api = ref.read(cisspApiProvider);
    final user = ref.read(authSessionProvider).user;
    try {
      if (examTargetDate != null) {
        await api.putPreferences(
          updateExamTargetDate: true,
          examTargetDate: examTargetDate,
        );
      }
      if (dailyGoalAnswers != null) {
        await api.putPreferences(
          updateDailyGoal: true,
          dailyGoalAnswers: dailyGoalAnswers,
        );
      }
      if (user != null) {
        await ref.read(authSessionProvider.notifier).setUser(
              copyUser(
                user,
                examTargetDate:
                    examTargetDate ?? user.examTargetDate, // null = keep
                dailyGoalAnswers:
                    dailyGoalAnswers ?? user.dailyGoalAnswers,
              ),
            );
      }
    } catch (e, s) {
      logError(e, s, 'settings:saveGoals');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context)!.commonErrorTitle)),
        );
      }
      return;
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.settingsSaved)),
      );
      setState(() {});
    }
  }

  Future<void> _clearExamDate() async {
    final api = ref.read(cisspApiProvider);
    final user = ref.read(authSessionProvider).user;
    try {
      await api.putPreferences(updateExamTargetDate: true, examTargetDate: null);
      if (user != null) {
        // Explicit null clears the local copy too (see copyUser sentinel).
        await ref.read(authSessionProvider.notifier).setUser(
              copyUser(user, examTargetDate: null),
            );
      }
    } catch (e, s) {
      logError(e, s, 'settings:clearExamDate');
    }
    if (mounted) setState(() {});
  }

  Future<void> _pickExamDate() async {
    final user = ref.read(authSessionProvider).user;
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate:
          (user?.examTargetDate != null && user!.examTargetDate!.isAfter(now))
              ? user.examTargetDate
              : now.add(const Duration(days: 30)),
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now.add(const Duration(days: 365 * 3)),
    );
    if (picked == null) return;
    await _saveGoals(examTargetDate: picked);
  }

  Future<void> _changePassword() async {
    final l10n = AppLocalizations.of(context)!;
    if (_next.text != _confirm.text) {
      setState(() => _pwdErr = l10n.settingsPasswordMismatch);
      return;
    }
    setState(() {
      _pwdBusy = true;
      _pwdErr = null;
      _pwdMsg = null;
    });
    try {
      await ref.read(cisspApiProvider).changePassword(
            currentPassword: _current.text,
            newPassword: _next.text,
          );
      _current.clear();
      _next.clear();
      _confirm.clear();
      setState(() => _pwdMsg = l10n.settingsPasswordChanged);
    } on DioException catch (e) {
      final err = ApiException.fromDio(e);
      setState(() {
        _pwdErr = err.status == 401 || err.status == 400
            ? l10n.settingsPasswordIncorrect
            : err.message;
      });
    } catch (e, s) {
      logError(e, s, 'settings:changePassword');
      setState(() => _pwdErr = l10n.commonErrorTitle);
    } finally {
      if (mounted) setState(() => _pwdBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final auth = ref.watch(authSessionProvider);
    final locale = ref.watch(localeControllerProvider);
    final contentMode = auth.user?.languageMode ?? 'en';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          l10n.settingsTitle,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
        ),
        const SizedBox(height: 4),
        Text(l10n.settingsDescription, style: const TextStyle(color: AppColors.muted)),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.settingsInterfaceTitle,
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(l10n.settingsInterfaceDesc,
                    style: const TextStyle(color: AppColors.muted)),
                const SizedBox(height: 12),
                SegmentedButton<String>(
                  segments: [
                    ButtonSegment(value: 'en', label: Text(l10n.langEn)),
                    ButtonSegment(value: 'zh', label: Text(l10n.langZh)),
                  ],
                  selected: {locale.languageCode},
                  onSelectionChanged: (s) => _setInterface(s.first),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.settingsContentTitle,
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(l10n.settingsContentDesc,
                    style: const TextStyle(color: AppColors.muted)),
                const SizedBox(height: 12),
                SegmentedButton<String>(
                  segments: [
                    ButtonSegment(value: 'en', label: Text(l10n.langEn)),
                    ButtonSegment(value: 'zh', label: Text(l10n.langZh)),
                    ButtonSegment(
                        value: 'bilingual', label: Text(l10n.langBilingual)),
                  ],
                  selected: {contentMode},
                  onSelectionChanged: (s) => _setContentMode(s.first),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.settingsGoalsTitle,
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(l10n.settingsGoalsDesc,
                    style: const TextStyle(color: AppColors.muted)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _pickExamDate,
                        child: Text(
                          auth.user?.examTargetDate != null
                              ? l10n.settingsExamDateValue(
                                  _fmtDate(auth.user!.examTargetDate!))
                              : l10n.settingsExamDateUnset,
                        ),
                      ),
                    ),
                    if (auth.user?.examTargetDate != null) ...[
                      const SizedBox(width: 8),
                      TextButton(
                        onPressed: _clearExamDate,
                        child: Text(l10n.settingsExamDateClear),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Text('${l10n.settingsDailyGoal}: '),
                    IconButton(
                      tooltip: l10n.settingsGoalLess,
                      onPressed: ((auth.user?.dailyGoalAnswers ?? 0) - 5) >= 1
                          ? () => _saveGoals(
                              dailyGoalAnswers:
                                  (auth.user?.dailyGoalAnswers ?? 20) - 5)
                          : null,
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                    Text(
                      '${auth.user?.dailyGoalAnswers ?? '—'}',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    IconButton(
                      tooltip: l10n.settingsGoalMore,
                      onPressed: ((auth.user?.dailyGoalAnswers ?? 0) + 5) <= 500
                          ? () => _saveGoals(
                              dailyGoalAnswers:
                                  (auth.user?.dailyGoalAnswers ?? 0) + 5)
                          : null,
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                    if (auth.user?.dailyGoalAnswers == null)
                      TextButton(
                        onPressed: () => _saveGoals(dailyGoalAnswers: 20),
                        child: Text(l10n.settingsGoalSet),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.settingsChangePasswordTitle,
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(l10n.settingsChangePasswordDesc,
                    style: const TextStyle(color: AppColors.muted)),
                const SizedBox(height: 12),
                TextField(
                  controller: _current,
                  obscureText: true,
                  decoration:
                      InputDecoration(labelText: l10n.settingsCurrentPassword),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _next,
                  obscureText: true,
                  decoration:
                      InputDecoration(labelText: l10n.settingsNewPassword),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _confirm,
                  obscureText: true,
                  decoration:
                      InputDecoration(labelText: l10n.settingsConfirmPassword),
                ),
                if (_pwdErr != null) ...[
                  const SizedBox(height: 8),
                  Text(_pwdErr!,
                      style: const TextStyle(color: AppColors.destructive)),
                ],
                if (_pwdMsg != null) ...[
                  const SizedBox(height: 8),
                  Text(_pwdMsg!, style: const TextStyle(color: AppColors.success)),
                ],
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _pwdBusy ? null : _changePassword,
                  child:
                      Text(_pwdBusy ? l10n.settingsUpdating : l10n.commonSave),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: () async {
            await ref.read(authSessionProvider.notifier).logout();
          },
          child: Text(l10n.navLogout),
        ),
        const LegalFooter(),
      ],
    );
  }
}

String _fmtDate(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class _Unset {
  const _Unset();
}

const _unset = _Unset();

/// Copy a [UserOut], overriding provided fields. Goal fields accept an
/// explicit `null` to CLEAR them (absent = keep), mirroring the API's
/// model_fields_set semantics.
UserOut copyUser(
  UserOut u, {
  String? languageMode,
  String? interfaceLanguage,
  Object? examTargetDate = _unset,
  Object? dailyGoalAnswers = _unset,
}) {
  return UserOut(
    id: u.id,
    email: u.email,
    displayName: u.displayName,
    roles: u.roles,
    perms: u.perms,
    languageMode: languageMode ?? u.languageMode,
    interfaceLanguage: interfaceLanguage ?? u.interfaceLanguage,
    examTargetDate:
        examTargetDate == _unset ? u.examTargetDate : examTargetDate as DateTime?,
    dailyGoalAnswers: dailyGoalAnswers == _unset
        ? u.dailyGoalAnswers
        : dailyGoalAnswers as int?,
  );
}
