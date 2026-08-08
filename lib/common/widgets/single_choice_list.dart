import 'package:PiliPlus/utils/device_utils.dart';
import 'package:flutter/material.dart';

/// 单选列表，内部消化 TV 与触屏的差异。
///
/// TV 上不能用 [RadioGroup]：它实现 W3C radio group 语义，把四个方向键全部绑到
/// 「选中上/下一项」（radio_group.dart 中 onChanged 与 requestFocus 同时发生），
/// 而遥控器只有方向键，结果是「焦点路过即选中」。TV 分支改用 [ListTile] + 单选
/// 图标，只有确定键触发的 onTap 才回调 [onChanged]。
///
/// 两个分支对外行为一致：选中某项时回调 [onChanged]。调用方若需要「预选 + 确定」
/// 的两步流程，在 [onChanged] 里自行决定是提交还是暂存。
class SingleChoiceList<T> extends StatelessWidget {
  const SingleChoiceList({
    super.key,
    required this.values,
    required this.selectedValue,
    required this.onChanged,
    required this.titleBuilder,
    this.subtitleBuilder,
    this.toggleable = false,
    this.dense = false,
    this.scrollable = false,
  });

  final List<T> values;
  final T? selectedValue;
  final ValueChanged<T?> onChanged;
  final Widget Function(BuildContext context, int index) titleBuilder;
  final Widget Function(BuildContext context, int index)? subtitleBuilder;

  /// 允许再次选中当前项以取消选择，此时 [onChanged] 收到 null。
  final bool toggleable;
  final bool dense;

  /// true 用 [ListView.builder]（需要外层给定高度约束），
  /// false 用 [Column]，适合放进 [SingleChildScrollView] 或对话框。
  final bool scrollable;

  Widget _buildList(
    Widget Function(BuildContext context, int index) itemBuilder,
  ) {
    if (scrollable) {
      return ListView.builder(
        itemCount: values.length,
        itemBuilder: itemBuilder,
      );
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        values.length,
        (index) => Builder(builder: (context) => itemBuilder(context, index)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (DeviceUtils.isTV) {
      return _buildList((context, index) {
        final item = values[index];
        final selected = item == selectedValue;
        final colorScheme = ColorScheme.of(context);
        return ListTile(
          dense: dense,
          leading: Icon(
            selected ? Icons.radio_button_checked : Icons.radio_button_off,
            color: selected ? colorScheme.primary : colorScheme.outline,
          ),
          title: titleBuilder(context, index),
          subtitle: subtitleBuilder?.call(context, index),
          onTap: () => onChanged(toggleable && selected ? null : item),
        );
      });
    }

    return RadioGroup<T>(
      onChanged: onChanged,
      groupValue: selectedValue,
      child: _buildList((context, index) {
        return RadioListTile<T>(
          toggleable: toggleable,
          dense: dense,
          value: values[index],
          title: titleBuilder(context, index),
          subtitle: subtitleBuilder?.call(context, index),
        );
      }),
    );
  }
}
