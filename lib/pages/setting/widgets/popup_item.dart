import 'package:PiliPlus/common/widgets/flutter/list_tile.dart';
import 'package:PiliPlus/models/common/enum_with_label.dart';
import 'package:PiliPlus/utils/device_utils.dart';
import 'package:PiliPlus/utils/platform_utils.dart';
import 'package:flutter/material.dart' hide ListTile;

typedef PopupMenuItemSelected<T> =
    void Function(T value, VoidCallback setState);

List<PopupMenuEntry<T>> enumItemBuilder<T extends EnumWithLabel>(
  List<T> items,
) => items.map((e) => PopupMenuItem(value: e, child: Text(e.label))).toList();

enum DescPosType { subtitle, title, trailing }

class PopupListTile<T> extends StatefulWidget {
  const PopupListTile({
    super.key,
    this.dense,
    this.safeArea = true,
    this.enabled = true,
    this.leading,
    required this.title,
    this.descPosType = .subtitle,
    required this.value,
    required this.itemBuilder,
    required this.onSelected,
    this.descFontSize = 13,
  });

  final bool? dense;
  final bool safeArea;
  final bool enabled;
  final Widget? leading;
  final Widget title;

  final DescPosType descPosType;
  final ValueGetter<(T, String)> value;
  final PopupMenuItemBuilder<T> itemBuilder;
  final PopupMenuItemSelected<T> onSelected;
  final double descFontSize;

  @override
  State<PopupListTile<T>> createState() => _PopupListTileState<T>();
}

class _PopupListTileState<T> extends State<PopupListTile<T>> {
  final _key = PlatformUtils.isDesktop ? null : GlobalKey();

  void _showButtonMenu(TapUpDetails details, T value) {
    final thisOffset = details.globalPosition - details.localPosition;
    final double dx;
    if (PlatformUtils.isDesktop) {
      dx = details.globalPosition.dx + 1;
    } else {
      final thisBox = context.findRenderObject() as RenderBox;
      final titleBox = _key!.currentContext!.findRenderObject() as RenderBox;
      final titleOffset = titleBox.localToGlobal(.zero, ancestor: thisBox);
      dx = thisOffset.dx + titleOffset.dx;
    }
    showMenu<T?>(
      context: context,
      position: RelativeRect.fromLTRB(dx, thisOffset.dy + 5, dx, 0),
      items: widget.itemBuilder(context),
      initialValue: value,
      requestFocus: false,
    ).then<void>((T? newValue) {
      if (!mounted) {
        return;
      }
      if (newValue == null || newValue == value) {
        return;
      }
      widget.onSelected(newValue, _refresh);
    });
  }

  /// TV 遥控器确定键激活：用组件中心位置弹出菜单，行为与触摸激活一致。
  void _showMenuFromCenter(T value) {
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return;
    final topLeft = box.localToGlobal(Offset.zero);
    final bottomRight = box.localToGlobal(box.size.bottomRight(Offset.zero));
    showMenu<T?>(
      context: context,
      position: RelativeRect.fromLTRB(
        topLeft.dx,
        topLeft.dy,
        bottomRight.dx,
        bottomRight.dy,
      ),
      items: widget.itemBuilder(context),
      initialValue: value,
    ).then<void>((T? newValue) {
      if (!mounted) return;
      if (newValue == null || newValue == value) return;
      widget.onSelected(newValue, _refresh);
    });
  }

  void _refresh() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (value, descStr) = widget.value();
    Widget title = KeyedSubtree(key: _key, child: widget.title);
    Widget? subtitle;
    Widget? trailing;
    final desc = Text(
      descStr,
      style: TextStyle(
        fontSize: widget.descFontSize,
        color: widget.enabled
            ? theme.colorScheme.secondary
            : theme.disabledColor,
      ),
    );
    switch (widget.descPosType) {
      case DescPosType.subtitle:
        subtitle = desc;
      case DescPosType.title:
        title = Row(
          spacing: 12,
          mainAxisSize: .min,
          children: [title, desc],
        );
      case DescPosType.trailing:
        trailing = desc;
    }
    return ListTile(
      dense: widget.dense,
      safeArea: widget.safeArea,
      enabled: widget.enabled,
      onTapUp: (details) => _showButtonMenu(details, value),
      // TV 遥控器确定键走 onTap 路径（不产生 TapUpDetails），用组件中心定位弹出菜单。
      onTap: DeviceUtils.isTV ? () => _showMenuFromCenter(value) : null,
      leading: widget.leading,
      title: title,
      subtitle: subtitle,
      trailing: trailing,
    );
  }
}
