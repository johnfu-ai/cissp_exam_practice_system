import 'package:flutter/material.dart';

import 'package:cissp_compass/design/theme.dart';

class ShellDestination {
  const ShellDestination({
    required this.label,
    required this.icon,
    this.selectedIcon,
  });

  final String label;
  final IconData icon;
  final IconData? selectedIcon;
}

/// Phone: bottom [NavigationBar]. Desktop (≥800): [NavigationRail] sidebar.
class AdaptiveScaffold extends StatelessWidget {
  const AdaptiveScaffold({
    super.key,
    required this.currentIndex,
    required this.onNavigate,
    required this.destinations,
    required this.child,
    this.title,
    this.actions,
    this.breakpoint = 800,
  });

  final int currentIndex;
  final ValueChanged<int> onNavigate;
  final List<ShellDestination> destinations;
  final Widget child;
  final String? title;
  final List<Widget>? actions;
  final double breakpoint;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= breakpoint;
        if (wide) {
          return Scaffold(
            backgroundColor: AppColors.canvas,
            body: Row(
              children: [
                NavigationRail(
                  selectedIndex: currentIndex.clamp(0, destinations.length - 1),
                  onDestinationSelected: onNavigate,
                  labelType: NavigationRailLabelType.all,
                  leading: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    child: Text(
                      'CISSP\nCompass',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: AppColors.primary,
                            height: 1.15,
                          ),
                    ),
                  ),
                  destinations: [
                    for (final d in destinations)
                      NavigationRailDestination(
                        icon: Icon(d.icon),
                        selectedIcon: Icon(d.selectedIcon ?? d.icon),
                        label: Text(d.label),
                      ),
                  ],
                ),
                const VerticalDivider(width: 1),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (title != null)
                        AppBar(
                          title: Text(title!),
                          actions: actions,
                          automaticallyImplyLeading: false,
                        ),
                      Expanded(child: child),
                    ],
                  ),
                ),
              ],
            ),
          );
        }

        return Scaffold(
          backgroundColor: AppColors.canvas,
          appBar: title == null
              ? null
              : AppBar(title: Text(title!), actions: actions),
          body: child,
          bottomNavigationBar: NavigationBar(
            selectedIndex: currentIndex.clamp(0, destinations.length - 1),
            onDestinationSelected: onNavigate,
            destinations: [
              for (final d in destinations)
                NavigationDestination(
                  icon: Icon(d.icon),
                  selectedIcon: Icon(d.selectedIcon ?? d.icon),
                  label: d.label,
                ),
            ],
          ),
        );
      },
    );
  }
}
