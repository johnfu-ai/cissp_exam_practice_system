import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cissp_compass/l10n/app_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:cissp_compass/core/providers.dart';
import 'package:cissp_compass/design/shell.dart';
import 'package:cissp_compass/features/analytics/analytics_screen.dart';
import 'package:cissp_compass/features/auth/forgot_password_screen.dart';
import 'package:cissp_compass/features/auth/login_screen.dart';
import 'package:cissp_compass/features/auth/register_screen.dart';
import 'package:cissp_compass/features/dashboard/dashboard_screen.dart';
import 'package:cissp_compass/features/exam/exam_screens.dart';
import 'package:cissp_compass/features/practice/practice_screens.dart';
import 'package:cissp_compass/features/review/review_screen.dart';
import 'package:cissp_compass/features/settings/settings_screen.dart';
import 'package:cissp_compass/features/shared/placeholder_screen.dart';

class _AuthRefresh extends ChangeNotifier {
  void ping() => notifyListeners();
}

final goRouterProvider = Provider<GoRouter>((ref) {
  final refresh = _AuthRefresh();
  ref.listen(authSessionProvider, (_, __) => refresh.ping());

  String? redirect(BuildContext context, GoRouterState state) {
    final auth = ref.read(authSessionProvider);
    if (!auth.hydrated) return null;

    final loc = state.matchedLocation;
    final isAuthRoute = loc == '/login' ||
        loc == '/register' ||
        loc == '/forgot-password';

    if (!auth.isAuthenticated && !isAuthRoute) return '/login';
    if (auth.isAuthenticated && isAuthRoute) return '/dashboard';
    if (loc == '/') return auth.isAuthenticated ? '/dashboard' : '/login';
    return null;
  }

  return GoRouter(
    initialLocation: '/dashboard',
    refreshListenable: refresh,
    redirect: redirect,
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
      GoRoute(
        path: '/forgot-password',
        builder: (_, __) => const ForgotPasswordScreen(),
      ),
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (_, __) => const DashboardScreen(),
          ),
          GoRoute(
            path: '/practice',
            builder: (_, __) => const PracticeHomeScreen(),
            routes: [
              GoRoute(
                path: 'sessions/:id',
                builder: (_, state) => PracticeRunnerScreen(
                  sessionId: state.pathParameters['id']!,
                ),
                routes: [
                  GoRoute(
                    path: 'done',
                    builder: (_, state) => PracticeDoneScreen(
                      sessionId: state.pathParameters['id']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          GoRoute(
            path: '/review',
            builder: (_, __) => const ReviewScreen(),
          ),
          GoRoute(
            path: '/exam',
            builder: (_, __) => const ExamHomeScreen(),
            routes: [
              GoRoute(
                path: 'sessions/:id',
                builder: (_, state) => ExamRunnerScreen(
                  sessionId: state.pathParameters['id']!,
                ),
                routes: [
                  GoRoute(
                    path: 'report',
                    builder: (_, state) => ExamReportScreen(
                      sessionId: state.pathParameters['id']!,
                    ),
                  ),
                  GoRoute(
                    path: 'review',
                    builder: (_, state) => ExamReviewScreen(
                      sessionId: state.pathParameters['id']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          GoRoute(
            path: '/analytics',
            builder: (_, __) => const AnalyticsScreen(),
          ),
          GoRoute(
            path: '/settings',
            builder: (_, __) => const SettingsScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/',
        builder: (_, __) => const PlaceholderScreen(title: 'CISSP Compass'),
      ),
    ],
  );
});

class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  static const _paths = [
    '/dashboard',
    '/practice',
    '/exam',
    '/review',
    '/settings',
  ];

  int _indexFor(String location) {
    for (var i = 0; i < _paths.length; i++) {
      if (location == _paths[i] || location.startsWith('${_paths[i]}/')) {
        return i;
      }
    }
    if (location.startsWith('/analytics')) return 0;
    return 0;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final location = GoRouterState.of(context).uri.path;
    final index = _indexFor(location);

    // Hide bottom nav on deep runners for focus.
    final hideNav = location.contains('/sessions/');

    if (hideNav) {
      return Scaffold(body: child);
    }

    return AdaptiveScaffold(
      currentIndex: index,
      onNavigate: (i) => context.go(_paths[i]),
      destinations: [
        ShellDestination(label: l10n.navHome, icon: Icons.home_outlined, selectedIcon: Icons.home),
        ShellDestination(label: l10n.navPractice, icon: Icons.fitness_center_outlined, selectedIcon: Icons.fitness_center),
        ShellDestination(label: l10n.navExam, icon: Icons.quiz_outlined, selectedIcon: Icons.quiz),
        ShellDestination(label: l10n.navReview, icon: Icons.bookmark_border, selectedIcon: Icons.bookmark),
        ShellDestination(label: l10n.navSettings, icon: Icons.settings_outlined, selectedIcon: Icons.settings),
      ],
      child: child,
    );
  }
}
