import 'package:PiliPlus/utils/device_utils.dart';
import 'package:PiliPlus/utils/extension/num_ext.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show LogicalKeyboardKey, KeyDownEvent;

class SliderDialog extends StatefulWidget {
  const SliderDialog({
    super.key,
    required this.value,
    required this.title,
    required this.min,
    required this.max,
    this.divisions,
    this.suffix = '',
    this.precise = 1,
  });

  final double value;
  final Widget title;
  final double min;
  final double max;
  final int? divisions;
  final String suffix;
  final int precise;

  @override
  State<SliderDialog> createState() => _SliderDialogState();
}

class _SliderDialogState extends State<SliderDialog> {
  late double _tempValue;
  final _cancelFocus = FocusNode();
  // TV 上直接把 FocusNode 传给 Slider 并重写 onKeyEvent，优先级高于 Slider 内部
  // 的 _AdjustSliderIntent Action，使上下键不被 Slider 消费而是跳到按钮区。
  late final _sliderFocus = DeviceUtils.isTV
      ? (FocusNode()
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
        })
      : null;

  @override
  void initState() {
    super.initState();
    _tempValue = widget.value;
  }

  @override
  void dispose() {
    _sliderFocus?.dispose();
    _cancelFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final slider = Slider(
      focusNode: _sliderFocus,
      value: _tempValue,
      min: widget.min,
      max: widget.max,
      divisions: widget.divisions,
      label: '${_tempValue.toStringAsFixed(widget.precise)}${widget.suffix}',
      onChanged: (double value) {
        setState(() {
          _tempValue = value.toPrecision(widget.precise);
        });
      },
    );

    return AlertDialog(
      title: widget.title,
      contentPadding: const .only(top: 20, left: 8, right: 8, bottom: 8),
      content: SizedBox(height: 40, child: slider),
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
          onPressed: () => Navigator.pop(context, _tempValue),
          child: const Text('确定'),
        ),
      ],
    );
  }
}
