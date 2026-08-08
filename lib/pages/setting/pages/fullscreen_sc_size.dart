import 'dart:io' show Platform;
import 'dart:math' as math;

import 'package:PiliPlus/common/widgets/custom_icon.dart';
import 'package:PiliPlus/common/widgets/extra_hittest_stack.dart';
import 'package:PiliPlus/common/widgets/scaffold/simple_scaffold.dart';
import 'package:PiliPlus/models_new/live/live_superchat/item.dart';
import 'package:PiliPlus/pages/live_room/superchat/superchat_card.dart';
import 'package:PiliPlus/plugin/pl_player/utils/fullscreen.dart';
import 'package:PiliPlus/utils/device_utils.dart';
import 'package:PiliPlus/utils/platform_utils.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:PiliPlus/utils/storage_key.dart';
import 'package:PiliPlus/utils/storage_pref.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart'
    show KeyDownEvent, KeyRepeatEvent, LogicalKeyboardKey;

const kFullScreenSCWidth = 255.0;

class FullScreenScSize extends StatefulWidget {
  const FullScreenScSize({super.key});

  @override
  State<FullScreenScSize> createState() => _FullScreenScSizeState();
}

class _FullScreenScSizeState extends State<FullScreenScSize> {
  double _width = Pref.fullScreenSCWidth;
  final _randomSC = SuperChatItem.random;
  late EdgeInsets _padding;
  late double _maxWidth;
  late ColorScheme _colorScheme;

  @override
  void initState() {
    super.initState();
    if (Platform.isAndroid) {
      landscapeLeftMode();
    } else if (Platform.isIOS) {
      landscapeRightMode();
    }
  }

  @override
  void dispose() {
    if (PlatformUtils.isMobile) {
      if (Pref.horizontalScreen) {
        fullMode();
      } else {
        portraitUpMode();
      }
    }
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final padding = MediaQuery.viewPaddingOf(context);
    _padding = .only(
      right: padding.right + 17,
      left: padding.left + 25,
      bottom: padding.bottom + 25,
    );
    _colorScheme = ColorScheme.of(context);
    // 可用宽度即卡片上限，否则长按右键会把卡片撑出屏幕。
    //
    // 必须再套一层下界：[_setWidth] 用 `clamp(_kMinWidth, _maxWidth)`，而
    // `num.clamp` 要求 lower <= upper，窗口极窄时 `width - padding` 可能小于
    // _kMinWidth，直接抛 ArgumentError。
    _maxWidth = math.max(
      _kMinWidth,
      MediaQuery.sizeOf(context).width - _padding.horizontal,
    );
  }

  void _onReset() {
    _width = kFullScreenSCWidth;
    GStorage.setting.delete(SettingBoxKey.fullScreenSCWidth);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return SimpleScaffold(
      appBar: AppBar(
        title: const Text('全屏 SC 大小设置'),
        actions: [
          TextButton(onPressed: _onReset, child: const Text('重置')),
        ],
      ),
      body: Padding(padding: _padding, child: _buildBody),
    );
  }

  Widget get _buildBody {
    return Align(
      alignment: .bottomLeft,
      child: ExtraHitTestStack(
        clipBehavior: .none,
        children: [
          SizedBox(
            width: _width,
            child: IgnorePointer(
              child: SuperChatCard(
                item: _randomSC,
                persistentSC: true,
              ),
            ),
          ),
          Positioned(
            top: 0,
            bottom: 0,
            right: -17,
            width: 34,
            child: MouseRegion(
              cursor: SystemMouseCursors.resizeRight,
              child: GestureDetector(
                behavior: .opaque,
                onHorizontalDragUpdate: _onHorizontalDragUpdate,
                onHorizontalDragEnd: _onHorizontalDragEnd,
                child: Focus(
                  // 拖拽手柄原本只响应指针拖动，遥控器没有指针，TV 上完全无法
                  // 调整。这里给它一个焦点节点，左右键按步长增减宽度；上下键返回
                  // ignored 交还焦点遍历，避免困在手柄上出不去。
                  autofocus: DeviceUtils.isTV,
                  onKeyEvent: DeviceUtils.isTV ? _onHandleKey : null,
                  child: Builder(
                    builder: (context) {
                      final hasFocus = Focus.of(context).hasFocus;
                      return DecoratedBox(
                        decoration: BoxDecoration(
                          shape: .circle,
                          color: _colorScheme.secondaryContainer.withValues(
                            alpha: .8,
                          ),
                          border: hasFocus
                              ? Border.all(
                                  color: _colorScheme.primary,
                                  width: 2,
                                )
                              : null,
                        ),
                        child: Icon(
                          size: 18,
                          CustomIcons.open_in_full_rotate_45,
                          color: _colorScheme.onSecondaryContainer,
                        ),
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  static const _kMinWidth = 25.0;
  static const _kStep = 10.0;

  /// 拖拽与按键两条路径唯一的宽度写入口，保证边界一致。
  ///
  /// 原先拖拽只有 `math.max(25, ...)` 下界、按键才有 `_maxWidth` 上界，同一个值
  /// 两套约束：用手指能把卡片拖出屏幕，用遥控器不能。
  ///
  /// 不在此处持久化：拖拽每帧都会调用，落盘应留在 [_onHorizontalDragEnd]，
  /// 按键路径则每次按下即存。
  void _setWidth(double width) {
    final clamped = width.clamp(_kMinWidth, _maxWidth);
    if (clamped == _width) return;
    setState(() {
      _width = clamped;
    });
  }

  void _onHorizontalDragUpdate(DragUpdateDetails details) {
    _setWidth(_width + details.delta.dx);
  }

  void _onHorizontalDragEnd(DragEndDetails details) {
    GStorage.setting.put(SettingBoxKey.fullScreenSCWidth, _width);
  }

  KeyEventResult _onHandleKey(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
      return KeyEventResult.ignored;
    }
    final key = event.logicalKey;
    final isLeft = key == LogicalKeyboardKey.arrowLeft;
    if (isLeft || key == LogicalKeyboardKey.arrowRight) {
      _setWidth(_width + (isLeft ? -_kStep : _kStep));
      GStorage.setting.put(SettingBoxKey.fullScreenSCWidth, _width);
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }
}
