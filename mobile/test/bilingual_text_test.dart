import 'package:cissp_api/cissp_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:cissp_compass/design/bilingual_text.dart';

void main() {
  testWidgets('BilingualText shows en only in en mode', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: BilingualText(
            text: Localized(en: 'Hello', zh: '你好'),
            mode: 'en',
          ),
        ),
      ),
    );
    expect(find.text('Hello'), findsOneWidget);
    expect(find.text('你好'), findsNothing);
  });

  testWidgets('BilingualText falls back when preferred language missing',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: BilingualText(
            text: Localized(en: 'Hello', zh: null),
            mode: 'zh',
          ),
        ),
      ),
    );
    expect(find.text('Hello'), findsOneWidget);
  });

  testWidgets('ExplanationPanel renders per-option explanations', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ExplanationPanel(
            mode: 'en',
            rationale: const Localized(en: 'Why A', zh: null),
            keyPoints: const Localized(en: 'KP', zh: null),
            perOption: const [
              PerOptionExplanation(
                orderIndex: 0,
                isCorrect: true,
                explanation: Localized(en: 'Option A why', zh: null),
              ),
            ],
            keyPointsLabel: 'Key points',
            optionExplanationsLabel: 'Option explanations',
          ),
        ),
      ),
    );
    expect(find.text('Why A'), findsOneWidget);
    expect(find.text('Key points'), findsOneWidget);
    expect(find.textContaining('Option A why'), findsOneWidget);
  });
}
