import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit({String? email, String? password}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(authSessionProvider.notifier).login(
            email: email ?? _email.text.trim(),
            password: password ?? _password.text,
          );
      if (mounted) context.go('/dashboard');
    } on ApiException catch (e) {
      setState(() {
        final l10n = AppLocalizations.of(context)!;
        if (e.status == 401) {
          _error = l10n.authInvalidCredentials;
        } else if (e.status == 429) {
          _error = l10n.authTooManyAttempts;
        } else if (e.status == 0) {
          _error = l10n.authNetworkError;
        } else {
          _error = e.message;
        }
      });
    } catch (_) {
      setState(() => _error = AppLocalizations.of(context)!.authNetworkError);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.canvas,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: [
                const SizedBox(height: 32),
                Text(
                  l10n.brandName,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: AppColors.primary,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  l10n.brandTagline,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppColors.muted,
                      ),
                ),
                const SizedBox(height: 32),
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  decoration: InputDecoration(
                    labelText: l10n.authEmail,
                    hintText: l10n.authEmailPlaceholder,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  obscureText: true,
                  autofillHints: const [AutofillHints.password],
                  onSubmitted: (_) => _busy ? null : _submit(),
                  decoration: InputDecoration(
                    labelText: l10n.authPassword,
                    hintText: l10n.authPasswordPlaceholder,
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: const TextStyle(color: AppColors.destructive),
                  ),
                ],
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _busy ? null : () => _submit(),
                  child: Text(_busy ? l10n.authLoggingIn : l10n.authLogin),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => _submit(email: 'admin@example.com', password: 'Adminadmin1'),
                  child: Text(l10n.authDevLogin),
                ),
                const SizedBox(height: 8),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 8,
                  children: [
                    TextButton(
                      onPressed: () => context.go('/forgot-password'),
                      child: Text(l10n.authForgotPassword),
                    ),
                    TextButton(
                      onPressed: () => context.go('/register'),
                      child: Text('${l10n.authNoAccount} ${l10n.authRegister}'),
                    ),
                  ],
                ),
                const LegalFooter(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
