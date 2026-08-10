import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Desktop keyboard shortcuts for practice / exam runners (FR-CLIENT-05).
///
/// - `1–4` / `A–D` select option by display slot
/// - `Enter` submit / next
/// - Arrow Left/Right navigate (fixed exam palette)
class RunnerShortcuts extends StatelessWidget {
  const RunnerShortcuts({
    super.key,
    required this.child,
    this.onSelectSlot,
    this.onSubmit,
    this.onPrev,
    this.onNext,
    this.enabled = true,
  });

  final Widget child;
  final void Function(int slot)? onSelectSlot;
  final VoidCallback? onSubmit;
  final VoidCallback? onPrev;
  final VoidCallback? onNext;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    if (!enabled) return child;

    return Focus(
      autofocus: true,
      child: CallbackShortcuts(
        bindings: <ShortcutActivator, VoidCallback>{
          for (var i = 0; i < 4; i++)
            CharacterActivator('${i + 1}'): () => onSelectSlot?.call(i),
          for (var i = 0; i < 4; i++)
            CharacterActivator(String.fromCharCode(65 + i)): () =>
                onSelectSlot?.call(i),
          for (var i = 0; i < 4; i++)
            CharacterActivator(String.fromCharCode(97 + i)): () =>
                onSelectSlot?.call(i),
          const SingleActivator(LogicalKeyboardKey.enter): () => onSubmit?.call(),
          const SingleActivator(LogicalKeyboardKey.arrowLeft): () =>
              onPrev?.call(),
          const SingleActivator(LogicalKeyboardKey.arrowRight): () =>
              onNext?.call(),
        },
        child: child,
      ),
    );
  }
}

/// True when the adaptive shell should enable keyboard shortcuts.
bool useDesktopShortcuts(BuildContext context, {double breakpoint = 800}) {
  return MediaQuery.sizeOf(context).width >= breakpoint;
}
