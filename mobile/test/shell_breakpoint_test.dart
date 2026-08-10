import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cissp_compass/design/shell.dart';

void main() {
  testWidgets('phone width uses NavigationBar', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);

    await tester.pumpWidget(
      MaterialApp(
        home: AdaptiveScaffold(
          currentIndex: 0,
          onNavigate: (_) {},
          destinations: const [
            ShellDestination(label: 'Home', icon: Icons.home),
            ShellDestination(label: 'Practice', icon: Icons.school),
          ],
          child: const Text('body'),
        ),
      ),
    );

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationRail), findsNothing);
  });

  testWidgets('desktop width uses NavigationRail', (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);

    await tester.pumpWidget(
      MaterialApp(
        home: AdaptiveScaffold(
          currentIndex: 0,
          onNavigate: (_) {},
          destinations: const [
            ShellDestination(label: 'Home', icon: Icons.home),
            ShellDestination(label: 'Practice', icon: Icons.school),
          ],
          child: const Text('body'),
        ),
      ),
    );

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });
}
