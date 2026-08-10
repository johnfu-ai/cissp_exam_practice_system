import 'package:flutter/material.dart';

/// Apple-aligned light palette matching the web product tokens.
abstract final class AppColors {
  static const primary = Color(0xFF007AFF);
  static const canvas = Color(0xFFF7F7FA);
  static const card = Color(0xFFFFFFFF);
  static const success = Color(0xFF157A3A); // WCAG AA on white (~web --success)
  static const warning = Color(0xFFFF9500);
  static const destructive = Color(0xFFD93838); // WCAG AA on white (~web --destructive)
  static const muted = Color(0xFF8E8E93);
  static const foreground = Color(0xFF1C1C1E);
  static const border = Color(0xFFE5E5EA);
}

ThemeData buildAppTheme() {
  const radius = 12.0;
  final scheme = ColorScheme.light(
    primary: AppColors.primary,
    onPrimary: Colors.white,
    secondary: AppColors.primary,
    onSecondary: Colors.white,
    error: AppColors.destructive,
    onError: Colors.white,
    surface: AppColors.card,
    onSurface: AppColors.foreground,
    surfaceContainerLowest: AppColors.canvas,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.canvas,
    canvasColor: AppColors.canvas,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.canvas,
      foregroundColor: AppColors.foreground,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: AppColors.card,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(radius),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.card,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(radius),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(radius),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(radius),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
        ),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.card,
      indicatorColor: AppColors.primary.withValues(alpha: 0.12),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(
          fontSize: 12,
          fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
          color: selected ? AppColors.primary : AppColors.muted,
        );
      }),
    ),
    navigationRailTheme: NavigationRailThemeData(
      backgroundColor: AppColors.card,
      selectedIconTheme: const IconThemeData(color: AppColors.primary),
      unselectedIconTheme: const IconThemeData(color: AppColors.muted),
      selectedLabelTextStyle: const TextStyle(
        color: AppColors.primary,
        fontWeight: FontWeight.w600,
      ),
      unselectedLabelTextStyle: const TextStyle(color: AppColors.muted),
      indicatorColor: AppColors.primary.withValues(alpha: 0.12),
    ),
    dividerColor: AppColors.border,
  );
}

extension AppThemeX on ThemeData {
  Color get success => AppColors.success;
  Color get warning => AppColors.warning;
  Color get destructive => AppColors.destructive;
  Color get mutedForeground => AppColors.muted;
}
