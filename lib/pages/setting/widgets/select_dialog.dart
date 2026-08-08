import 'package:PiliPlus/common/widgets/single_choice_list.dart';
import 'package:PiliPlus/models/common/video/cdn_type.dart';
import 'package:PiliPlus/models/video/play/url.dart';
import 'package:PiliPlus/utils/cdn_speed_service.dart';
import 'package:PiliPlus/utils/device_utils.dart';
import 'package:PiliPlus/utils/storage_pref.dart';
import 'package:PiliPlus/utils/video_utils.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';

class SelectDialog<T> extends StatefulWidget {
  final T? value;
  final String title;
  final List<(T, String)> values;
  final Widget Function(BuildContext, int)? subtitleBuilder;
  final bool toggleable;

  const SelectDialog({
    super.key,
    this.value,
    required this.values,
    required this.title,
    this.subtitleBuilder,
    this.toggleable = false,
  });

  @override
  State<SelectDialog<T>> createState() => _SelectDialogState<T>();
}

class _SelectDialogState<T> extends State<SelectDialog<T>> {
  // TV 上用两步流程：方向键只移动焦点（更新 _pendingValue），确定键才提交。
  // 非 TV 保持原来的「焦点即选中立刻 pop」行为。
  late T? _pendingValue;
  late final List<T> _itemValues;

  @override
  void initState() {
    super.initState();
    _pendingValue = widget.value;
    _itemValues = widget.values.map((e) => e.$1).toList();
  }

  @override
  Widget build(BuildContext context) {
    final titleMedium = TextTheme.of(context).titleMedium!;
    final isTV = DeviceUtils.isTV;
    return AlertDialog(
      clipBehavior: Clip.hardEdge,
      title: Text(widget.title),
      constraints: widget.subtitleBuilder != null
          ? const BoxConstraints.tightFor(width: 320)
          : null,
      contentPadding: const EdgeInsets.symmetric(vertical: 12),
      content: Material(
        type: .transparency,
        child: SingleChildScrollView(
          child: SingleChoiceList<T>(
            values: _itemValues,
            selectedValue: _pendingValue,
            toggleable: widget.toggleable,
            dense: true,
            // TV：只预选，等「确定」按钮提交。非 TV：选中即关闭。
            onChanged: isTV
                ? (v) => setState(() => _pendingValue = v)
                : (v) => Navigator.of(context).pop(v ?? widget.value),
            titleBuilder: (context, index) =>
                Text(widget.values[index].$2, style: titleMedium),
            subtitleBuilder: widget.subtitleBuilder,
          ),
        ),
      ),
      // TV 模式下显示「取消/确定」按钮，非 TV 无按钮（点击即关闭）。
      actions: isTV
          ? [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(
                  '取消',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
              ),
              TextButton(
                // toggleable 取消选择时 _pendingValue 为 null，调用方将其视为
                // 「不做改动」，与取消一致，故直接提交而不回退为原值。
                onPressed: () => Navigator.of(context).pop(_pendingValue),
                child: const Text('确定'),
              ),
            ]
          : null,
    );
  }
}

class CdnSelectDialog extends StatefulWidget {
  final BaseItem? sample;

  const CdnSelectDialog({
    super.key,
    this.sample,
  });

  @override
  State<CdnSelectDialog> createState() => _CdnSelectDialogState();
}

class _CdnSelectDialogState extends State<CdnSelectDialog> {
  late final List<ValueNotifier<String?>> _cdnResList;
  late final bool _cdnSpeedTest;
  CancelToken? _cancelToken;

  @override
  void initState() {
    _cdnSpeedTest = Pref.cdnSpeedTest;
    if (_cdnSpeedTest) {
      final length = CDNService.values.length;
      _cdnResList = List.generate(
        length,
        (_) => ValueNotifier<String?>(null),
      );
      _cancelToken = CancelToken();
      _startSpeedTest();
    }
    super.initState();
  }

  @override
  void dispose() {
    _cancelToken?.cancel();
    if (_cdnSpeedTest) {
      for (final notifier in _cdnResList) {
        notifier.dispose();
      }
    }
    super.dispose();
  }

  Future<void> _startSpeedTest() async {
    final token = _cancelToken;
    if (token == null) return;
    try {
      final videoItem = widget.sample ?? await CdnSpeedService.getSampleUrl();
      if (token.isCancelled || !mounted) return;
      await CdnSpeedService.testAll(
        videoItem,
        cancelToken: token,
        onProgress: (service, result) {
          if (token.isCancelled || !mounted) return;
          _cdnResList[service.index].value = result;
        },
      );
    } catch (e) {
      if (kDebugMode) debugPrint('CDN speed test failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return SelectDialog<CDNService>(
      title: 'CDN 设置',
      values: CDNService.values.map((i) => (i, i.desc)).toList(),
      value: VideoUtils.cdnService,
      subtitleBuilder: _cdnSpeedTest
          ? (context, index) {
              final item = _cdnResList[index];
              return ValueListenableBuilder(
                valueListenable: item,
                builder: (context, value, _) {
                  return Text(
                    value ?? '---',
                    style: const TextStyle(fontSize: 13),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  );
                },
              );
            }
          : null,
    );
  }
}
