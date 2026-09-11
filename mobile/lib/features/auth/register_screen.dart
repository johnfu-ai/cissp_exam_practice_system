import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/crash_reporting.dart';
import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _displayName = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _displayName.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final name = _displayName.text.trim();
      await ref.read(authSessionProvider.notifier).register(
            email: _email.text.trim(),
            password: _password.text,
            displayName: name.isEmpty ? null : name,
          );
      if (mounted) context.go('/dashboard');
    } on ApiException catch (e) {
      setState(() {
        final l10n = AppLocalizations.of(context)!;
        if (e.status == 409) {
          _error = l10n.authEmailExists;
        } else if (e.status == 0) {
          _error = l10n.authNetworkError;
        } else {
          _error = e.message.isNotEmpty ? e.message : l10n.authRegisterFailed;
        }
      });
    } catch (e, s) {
      logError(e, s, 'register:submit');
      setState(() => _error = AppLocalizations.of(context)!.authRegisterFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(title: Text(l10n.authRegister)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: InputDecoration(labelText: l10n.authEmail),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _displayName,
                decoration: InputDecoration(
                  labelText: '${l10n.authDisplayName} (${l10n.authOptional})',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _password,
                obscureText: true,
                decoration: InputDecoration(
                  labelText: l10n.authPassword,
                  helperText: l10n.authPasswordHint,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.destructive)),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: Text(_busy ? l10n.commonLoading : l10n.authRegister),
              ),
              TextButton(
                onPressed: () => context.go('/login'),
                child: Text('${l10n.authHaveAccount} ${l10n.authLogin}'),
              ),
              const LegalFooter(),
            ],
          ),
        ),
      ),
    );
  }
}
