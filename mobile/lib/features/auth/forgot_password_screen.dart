import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/errors.dart';
import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/legal_footer.dart';
import 'package:cissp_compass/design/theme.dart';

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _email = TextEditingController();
  final _token = TextEditingController();
  final _password = TextEditingController();
  bool _sent = false;
  bool _busy = false;
  String? _message;
  String? _error;
  String? _devToken;

  @override
  void dispose() {
    _email.dispose();
    _token.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _request() async {
    setState(() {
      _busy = true;
      _error = null;
      _message = null;
    });
    try {
      final api = ref.read(cisspApiProvider);
      final data = await api.requestPasswordReset(_email.text.trim());
      final token = data['token'] as String?;
      // The API only returns the token in dev/test environments; mirror that
      // on the client and never surface it in production builds.
      final showDevToken = ref.read(devConveniencesProvider);
      setState(() {
        _sent = true;
        _devToken = showDevToken ? token : null;
        _message = AppLocalizations.of(context)!.authResetSent;
        if (token != null && showDevToken) _token.text = token;
      });
    } on DioException catch (e) {
      setState(() => _error = ApiException.fromDio(e).message);
    } catch (_) {
      setState(() => _error = AppLocalizations.of(context)!.authNetworkError);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(cisspApiProvider).confirmPasswordReset(
            token: _token.text.trim(),
            newPassword: _password.text,
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context)!.authPasswordReset)),
        );
        context.go('/login');
      }
    } on DioException catch (e) {
      final msg = ApiException.fromDio(e).message;
      setState(() {
        _error = msg.isNotEmpty
            ? msg
            : AppLocalizations.of(context)!.authResetFailed;
      });
    } catch (_) {
      setState(() => _error = AppLocalizations.of(context)!.authResetFailed);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(title: Text(l10n.authForgotPasswordTitle)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(l10n.authForgotPasswordDesc),
              const SizedBox(height: 16),
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: InputDecoration(labelText: l10n.authEmail),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _busy ? null : _request,
                child: Text(_busy && !_sent ? l10n.authSending : l10n.authSendResetLink),
              ),
              if (_message != null) ...[
                const SizedBox(height: 12),
                Text(_message!),
              ],
              if (_devToken != null) ...[
                const SizedBox(height: 8),
                SelectableText('${l10n.authResetToken}: $_devToken'),
              ],
              if (_sent) ...[
                const SizedBox(height: 24),
                TextField(
                  controller: _token,
                  decoration: InputDecoration(
                    labelText: l10n.authResetToken,
                    hintText: l10n.authResetTokenPlaceholder,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  obscureText: true,
                  decoration: InputDecoration(labelText: l10n.authNewPassword),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _busy ? null : _confirm,
                  child: Text(_busy ? l10n.authResetting : l10n.authConfirmReset),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.destructive)),
              ],
              TextButton(
                onPressed: () => context.go('/login'),
                child: Text(l10n.authBackToLogin),
              ),
              const LegalFooter(),
            ],
          ),
        ),
      ),
    );
  }
}
