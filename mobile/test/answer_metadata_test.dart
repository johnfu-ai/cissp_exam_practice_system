import 'package:test/test.dart';

import 'package:cissp_compass/features/practice/answer_metadata.dart';

void main() {
  group('mappingLabelsFrom', () {
    test('prefers name keys and skips bare ids', () {
      final labels = mappingLabelsFrom({
        'domain_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        'domain_name': 'Security and Risk Management',
        'chapter_id': '11111111-2222-3333-4444-555555555555',
        'chapter_title': 'Chapter 1: Security Governance',
        'knowledge_point_id': '99999999-8888-7777-6666-555555555555',
        'knowledge_point_name': 'Risk assessment',
      });
      expect(labels.map((l) => l.kind).toList(), [
        'domain',
        'chapter',
        'knowledge_point',
      ]);
      expect(labels.map((l) => l.value).toList(), [
        'Security and Risk Management',
        'Chapter 1: Security Governance',
        'Risk assessment',
      ]);
    });

    test('returns empty when only uuid fields are present', () {
      expect(
        mappingLabelsFrom({
          'domain_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
          'chapter_id': null,
          'knowledge_point_id': null,
        }),
        isEmpty,
      );
    });

    test('accepts alternate name key spellings', () {
      final labels = mappingLabelsFrom({
        'domain': 'IAM',
        'chapter_name': 'Access Control',
        'kp_name': 'MFA',
      });
      expect(labels.length, 3);
      expect(labels[0].value, 'IAM');
      expect(labels[1].value, 'Access Control');
      expect(labels[2].value, 'MFA');
    });
  });

  group('historyAttemptsFrom + formatRelativePast', () {
    test('parses correctness and answered_at', () {
      final rows = historyAttemptsFrom([
        {
          'session_id': 's1',
          'is_correct': true,
          'answered_at': '2026-08-01T12:00:00Z',
        },
        {
          'session_id': 's2',
          'is_correct': false,
          'answered_at': null,
        },
      ]);
      expect(rows.length, 2);
      expect(rows[0].isCorrect, isTrue);
      expect(rows[0].answeredAt, isNotNull);
      expect(rows[1].isCorrect, isFalse);
      expect(rows[1].answeredAt, isNull);
    });

    test('formatRelativePast buckets by age', () {
      final now = DateTime.utc(2026, 8, 10, 12);
      expect(
        formatRelativePast(now.subtract(const Duration(seconds: 10)), now),
        'just now',
      );
      expect(
        formatRelativePast(now.subtract(const Duration(minutes: 5)), now),
        '5m ago',
      );
      expect(
        formatRelativePast(now.subtract(const Duration(hours: 3)), now),
        '3h ago',
      );
      expect(
        formatRelativePast(now.subtract(const Duration(days: 2)), now),
        '2d ago',
      );
    });
  });
}
