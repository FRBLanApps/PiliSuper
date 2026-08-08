import 'package:PiliPlus/utils/device_utils.dart';
import 'package:flutter/gestures.dart' show kBackMouseButton;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show KeyDownEvent, LogicalKeyboardKey;

class BackDetector extends StatelessWidget {
  const BackDetector({
    super.key,
    required this.onBack,
    required this.child,
  });

  final Widget child;

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Focus(
      canRequestFocus: false,
      onKeyEvent: _onKeyEvent,
      child: Listener(
        behavior: .translucent,
        onPointerDown: _onPointerDown,
        child: child,
      ),
    );
  }

  KeyEventResult _onKeyEvent(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent) return .ignored;

    if (DeviceUtils.isTV) {
      final focused = FocusManager.instance.primaryFocus;
      final focusedWidget = focused?.context?.widget;
      final isInTextField = focusedWidget is EditableText;

      // 遥控器确定键（select）：若焦点在输入框则弹出软键盘；
      // Android TV 软键盘不会随焦点自动弹出，需要用户主动按确定键触发。
      if (event.logicalKey == LogicalKeyboardKey.select) {
        if (isInTextField && focused != null) {
          // 调用 requestKeyboard 打开软键盘
          final state = focused.context?.findAncestorStateOfType<EditableTextState>();
          state?.requestKeyboard();
          return .handled;
        }
        return .ignored;
      }

      // 返回键（escape）：若焦点在输入框则 unfocus 退出编辑模式，
      // 否则正常执行页面返回。
      if (event.logicalKey == .escape) {
        if (isInTextField) {
          focused!.unfocus();
          return .handled;
        }
        onBack();
        return .handled;
      }

      return .ignored;
    }

    if (event.logicalKey == .escape) {
      onBack();
      return .handled;
    }
    return .ignored;
  }

  void _onPointerDown(PointerDownEvent event) {
    if (event.buttons == kBackMouseButton) {
      onBack();
    }
  }
}
