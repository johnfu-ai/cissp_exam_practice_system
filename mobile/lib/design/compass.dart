import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'package:cissp_compass/design/theme.dart';

/// One wedge of the Domain Compass (domain number + accuracy 0–1).
class CompassSegment {
  const CompassSegment({required this.number, required this.accuracy});

  final int number;
  final double accuracy;
}

/// Eight-segment domain mastery compass (custom painter).
class DomainCompass extends StatelessWidget {
  const DomainCompass({
    super.key,
    required this.segments,
    this.size = 220,
  });

  final List<CompassSegment> segments;
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _DomainCompassPainter(segments: segments),
      ),
    );
  }
}

class _DomainCompassPainter extends CustomPainter {
  _DomainCompassPainter({required this.segments});

  final List<CompassSegment> segments;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2;
    const count = 8;
    final sweep = (2 * math.pi) / count;
    final start = -math.pi / 2;

    final byNumber = {for (final s in segments) s.number: s};

    for (var i = 0; i < count; i++) {
      final number = i + 1;
      final seg = byNumber[number];
      final accuracy = seg?.accuracy ?? 0.0;
      final color = _colorFor(accuracy);

      final paint = Paint()
        ..color = color.withValues(alpha: 0.85)
        ..style = PaintingStyle.fill;

      final path = Path()
        ..moveTo(center.dx, center.dy)
        ..arcTo(
          Rect.fromCircle(center: center, radius: radius * 0.92),
          start + i * sweep,
          sweep,
          false,
        )
        ..close();
      canvas.drawPath(path, paint);

      final border = Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;
      canvas.drawPath(path, border);

      final mid = start + i * sweep + sweep / 2;
      final labelR = radius * 0.62;
      final lp = Offset(
        center.dx + labelR * math.cos(mid),
        center.dy + labelR * math.sin(mid),
      );
      final tp = TextPainter(
        text: TextSpan(
          text: '$number',
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, lp - Offset(tp.width / 2, tp.height / 2));
    }

    canvas.drawCircle(
      center,
      radius * 0.22,
      Paint()..color = AppColors.card,
    );
    canvas.drawCircle(
      center,
      radius * 0.22,
      Paint()
        ..color = AppColors.border
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );
  }

  Color _colorFor(double accuracy) {
    if (accuracy <= 0) return AppColors.muted;
    if (accuracy >= 0.8) return AppColors.success;
    if (accuracy >= 0.6) return AppColors.primary;
    if (accuracy >= 0.4) return AppColors.warning;
    return AppColors.destructive;
  }

  @override
  bool shouldRepaint(covariant _DomainCompassPainter oldDelegate) {
    if (oldDelegate.segments.length != segments.length) return true;
    for (var i = 0; i < segments.length; i++) {
      final a = oldDelegate.segments[i];
      final b = segments[i];
      if (a.number != b.number || a.accuracy != b.accuracy) return true;
    }
    return false;
  }
}
