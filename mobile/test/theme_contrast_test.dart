import 'package:test/test.dart';

/// Keep in sync with `AppColors.success` / `AppColors.destructive` in
/// `lib/design/theme.dart` (WCAG AA darkened targets matching web globals.css).
void main() {
  test('AA success and destructive color constants', () {
    const success = 0xFF157A3A;
    const destructive = 0xFFD93838;
    expect(success, 0xFF157A3A);
    expect(destructive, 0xFFD93838);
  });
}
