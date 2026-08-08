import 'package:PiliPlus/utils/device_utils.dart';
import 'package:PiliPlus/utils/extension/num_ext.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show LogicalKeyboardKey, KeyDownEvent;

class DualSliderDialog extends StatefulWidget {
  final double value1;
  final double value2;
  final Widget title;
  final Widget description1;
  final Widget description2;
  final double min;
  final double max;
  final int? divisions;
  final String suffix;
  final int precise;

  const DualSliderDialog({
    super.key,
    required this.value1,
    required this.value2,
    required this.description1,
    required this.description2,
    required this.title,
    required this.min,
    required this.max,
    this.divisions,
    this.suffix = '',
    this.precise = 1,
  });

  @override
  State<DualSliderDialog> createState() => _DualSliderDialogState();
}

class _DualSliderDialogState extends State<DualSliderDialog> {
  late double _tempValue1;
  late double _tempValue2;
  final _cancelFocus = FocusNode();

  // TV 上直接把 FocusNode 传给 Slider 并重写 onKeyEvent，优先于 Slider 内部
  // 的 _AdjustSliderIntent Action，使上下键跳到下一个节点而非被 Slider 消费。
  late final FocusNode? _slider1Focus;
  late final FocusNode? _slider2Focus;

  @override
  void initState() {
    super.initState();
    _tempValue1 = widget.value1;
    _tempValue2 = widget.value2;
    if (DeviceUtils.isTV) {
      final slider2Focus = FocusNode();
      _slider2Focus = slider2Focus
        ..onKeyEvent = (node, event) {
          if (event is KeyDownEvent) {
            final key = event.logicalKey;
            if (key == LogicalKeyboardKey.arrowDown ||
                key == LogicalKeyboardKey.arrowUp) {
              _cancelFocus.requestFocus();
              return KeyEventResult.handled;
            }
          }
          return KeyEventResult.ignored;
        };
      _slider1Focus = FocusNode()
        ..onKeyEvent = (node, event) {
          if (event is KeyDownEvent) {
            final key = event.logicalKey;
            if (key == LogicalKeyboardKey.arrowDown ||
                key == LogicalKeyboardKey.arrowUp) {
              slider2Focus.requestFocus();
              return KeyEventResult.handled;
            }
          }
          return KeyEventResult.ignored;
        };
    } else {
      _slider1Focus = null;
      _slider2Focus = null;
    }
  }

  @override
  void dispose() {
    _slider1Focus?.dispose();
    _slider2Focus?.dispose();
    _cancelFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: widget.title,
      contentPadding: const EdgeInsets.only(
        top: 20,
        left: 8,
        right: 8,
        bottom: 8,
      ),
      content: Column(
        mainAxisSize: .min,
        children: [
          widget.description1,
          Builder(
            builder: (context) {
              return Slider(
                focusNode: _slider1Focus,
                value: _tempValue1,
                min: widget.min,
                max: widget.max,
                divisions: widget.divisions,
                label:
                    '${_tempValue1.toStringAsFixed(widget.precise)}${widget.suffix}',
                onChanged: (double value) {
                  _tempValue1 = value.toPrecision(widget.precise);
                  (context as Element).markNeedsBuild();
                },
              );
            },
          ),
          widget.description2,
          Builder(
            builder: (context) {
              return Slider(
                focusNode: _slider2Focus,
                value: _tempValue2,
                min: widget.min,
                max: widget.max,
                divisions: widget.divisions,
                label:
                    '${_tempValue2.toStringAsFixed(widget.precise)}${widget.suffix}',
                onChanged: (double value) {
                  _tempValue2 = value.toPrecision(widget.precise);
                  (context as Element).markNeedsBuild();
                },
              );
            },
          ),
        ],
      ),
      actions: [
        TextButton(
          focusNode: _cancelFocus,
          onPressed: Navigator.of(context).pop,
          child: Text(
            '取消',
            style: TextStyle(color: Theme.of(context).colorScheme.outline),
          ),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context, (_tempValue1, _tempValue2)),
          child: const Text('确定'),
        ),
      ],
    );
  }
}
