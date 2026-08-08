import 'package:flutter/material.dart';

class PublishRoute<T> extends PopupRoute<T> {
  PublishRoute({
    required this.pageBuilder,
    this._barrierDismissible = true,
    this._barrierLabel,
    this._barrierColor = const Color(0x80000000),
    this._transitionDuration = const Duration(milliseconds: 500),
    this._transitionBuilder,
    super.settings,
  });

  final RoutePageBuilder pageBuilder;

  @override
  bool get barrierDismissible => _barrierDismissible;
  final bool _barrierDismissible;

  @override
  String? get barrierLabel => _barrierLabel;
  final String? _barrierLabel;

  @override
  Color get barrierColor => _barrierColor;
  final Color _barrierColor;

  @override
  Duration get transitionDuration => _transitionDuration;
  final Duration _transitionDuration;

  final RouteTransitionsBuilder? _transitionBuilder;

  @override
  Widget buildPage(
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
  ) {
    return Semantics(
      scopesRoute: true,
      explicitChildNodes: true,
      // PopupRoute 不像 Scaffold 那样提供 Material 祖先，而各发布面板内的 InkWell
      // （TV 遥控器聚焦所需）缺少 Material 会在运行时抛 `No Material widget found`。
      // 在此统一补一层透明 Material，覆盖所有经本路由挂载的面板。
      child: Material(
        type: MaterialType.transparency,
        child: pageBuilder(context, animation, secondaryAnimation),
      ),
    );
  }

  @override
  Widget buildTransitions(
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    if (_transitionBuilder != null) {
      return _transitionBuilder(context, animation, secondaryAnimation, child);
    }
    return SlideTransition(
      position: animation.drive(
        Tween<Offset>(
          begin: const Offset(0.0, 1.0),
          end: Offset.zero,
        ),
      ),
      child: child,
    );
  }
}
