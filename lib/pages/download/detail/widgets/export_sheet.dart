import 'dart:io' show Platform;

import 'package:PiliPlus/models/common/export_mode.dart';
import 'package:PiliPlus/models_new/download/bili_download_entry_info.dart';
import 'package:PiliPlus/services/export/cache_export_service.dart';
import 'package:PiliPlus/utils/export/export_target.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';
import 'package:material_ui/material_ui.dart';

/// 进度对话框的 tag，用于「后台运行」与结束时定向关闭。
const String _progressTag = 'cache_export_progress';

/// 打开导出选项面板。
Future<void> showExportSheet({
  required BuildContext context,
  required BiliDownloadEntryInfo entry,
}) async {
  final available = ExportMode.values
      .where((mode) => CacheExportService.isModeAvailable(entry, mode))
      .toList();
  if (available.isEmpty) {
    SmartDialog.showToast('该缓存暂不支持导出');
    return;
  }
  await showDialog<void>(
    context: context,
    builder: (context) => _ExportDialog(entry: entry, available: available),
  );
}

class _ExportDialog extends StatefulWidget {
  const _ExportDialog({required this.entry, required this.available});

  final BiliDownloadEntryInfo entry;
  final List<ExportMode> available;

  @override
  State<_ExportDialog> createState() => _ExportDialogState();
}

class _ExportDialogState extends State<_ExportDialog> {
  late final Set<ExportMode> _selected = {
    if (widget.available.contains(ExportMode.muxed))
      ExportMode.muxed
    else
      widget.available.first,
  };

  /// 缓存有封面时，合并输出会顺带写入封面。
  bool get _hasCover => widget.available.contains(ExportMode.cover);

  /// 缓存有弹幕文件时，才能内嵌软字幕轨。
  bool get _hasDanmaku => widget.available.contains(ExportMode.danmaku);

  /// 选中了会产出弹幕相关内容的模式（单独的 ASS 或内嵌软字幕轨）。
  bool get _usesDanmaku =>
      _selected.contains(ExportMode.danmaku) ||
      _selected.contains(ExportMode.muxed);

  String? _location;

  @override
  void initState() {
    super.initState();
    // exportTargetLabel 只在切换时刷新，这里直接以缓存值起手再异步校正。
    _location = exportTargetLabel.isEmpty ? null : exportTargetLabel;
    _loadLocation();
  }

  Future<void> _loadLocation() async {
    final label = await exportTarget.displayLabel();
    if (mounted) {
      setState(() => _location = label);
    }
  }

  void _toggle(ExportMode mode, bool checked) {
    setState(() {
      if (!checked) {
        _selected.remove(mode);
        return;
      }
      // 两个完整输出互斥，避免重复转封装同一份内容。
      if (mode.isCombined) {
        _selected.removeWhere((e) => e.isCombined);
      }
      _selected.add(mode);
    });
  }

  Future<void> _start() async {
    // 先取出所需数据：关闭对话框会销毁本 State，而导出仍在继续。
    final entry = widget.entry;
    final modes = Set<ExportMode>.from(_selected);
    Get.back();
    final service = Get.find<CacheExportService>();
    showExportProgressDialog(service);
    final results = await service.export(entry: entry, modes: modes);
    if (SmartDialog.checkExist(tag: _progressTag)) {
      await SmartDialog.dismiss(tag: _progressTag);
    }
    _showSummary(results);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: const Text('导出缓存'),
      contentPadding: const EdgeInsets.symmetric(vertical: 12),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final mode in widget.available)
              CheckboxListTile(
                dense: true,
                value: _selected.contains(mode),
                title: Text(mode.label, style: const TextStyle(fontSize: 14)),
                subtitle: switch (mode) {
                  ExportMode.muxed when _hasDanmaku => Text(
                    _hasCover ? '含弹幕软字幕轨与封面' : '含弹幕软字幕轨',
                    style: TextStyle(
                      fontSize: 12,
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  ExportMode.muxed when _hasCover => Text(
                    '含封面',
                    style: TextStyle(
                      fontSize: 12,
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  ExportMode.videoAudio when _hasCover => Text(
                    '含封面',
                    style: TextStyle(
                      fontSize: 12,
                      color: theme.colorScheme.outline,
                    ),
                  ),
                  _ => null,
                },
                onChanged: (checked) => _toggle(mode, checked ?? false),
              ),
            if (_usesDanmaku)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: Text(
                  '高级弹幕与 BAS 弹幕暂不支持导出，将自动忽略',
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.outline,
                  ),
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text(
                '导出至：${_location ?? '读取中…'}',
                style: TextStyle(
                  fontSize: 12,
                  color: theme.colorScheme.outline,
                ),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: Get.back,
          child: Text(
            '取消',
            style: TextStyle(color: theme.colorScheme.outline),
          ),
        ),
        TextButton(
          onPressed: _selected.isEmpty ? null : _start,
          child: const Text('开始导出'),
        ),
      ],
    );
  }
}

/// 导出进度。
///
/// 「后台运行」只收起对话框，任务继续；Android 上由前台服务在通知栏续报进度，
/// 其他平台窗口保持存活即可。
void showExportProgressDialog(CacheExportService service) {
  SmartDialog.show(
    tag: _progressTag,
    clickMaskDismiss: false,
    keepSingle: true,
    builder: (context) {
      final theme = Theme.of(context);
      return AlertDialog(
        title: const Text('正在导出'),
        content: Obx(() {
          final progress = service.progress.value;
          return Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 12,
            children: [
              Text(
                '${service.stage.value.message}'
                '${service.currentLabel.value.isEmpty ? '' : ' · ${service.currentLabel.value}'}',
                style: const TextStyle(fontSize: 14),
              ),
              LinearProgressIndicator(
                value: progress < 0 ? null : progress,
              ),
              if (progress >= 0)
                Text(
                  '${(progress * 100).toStringAsFixed(1)}%',
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.outline,
                  ),
                ),
              Text(
                Platform.isAndroid ? '可切至后台运行，进度会显示在通知栏' : '请保持应用运行，退出将中断导出',
                style: TextStyle(
                  fontSize: 12,
                  color: theme.colorScheme.outline,
                ),
              ),
            ],
          );
        }),
        actions: [
          TextButton(
            onPressed: () {
              SmartDialog.dismiss(tag: _progressTag);
              SmartDialog.showToast(
                Platform.isAndroid ? '已转入后台，可在通知栏查看进度' : '已转入后台运行',
              );
            },
            child: const Text('后台运行'),
          ),
          TextButton(
            onPressed: () {
              service.cancel();
              SmartDialog.showToast('正在取消…');
            },
            child: Text(
              '取消导出',
              style: TextStyle(color: theme.colorScheme.error),
            ),
          ),
        ],
      );
    },
  );
}

void _showSummary(List<ExportItemResult> results) {
  if (results.isEmpty) return;
  final succeeded = results.where((e) => e.isSuccess).toList();
  final cancelled = results.where((e) => e.cancelled).toList();
  final failed = results.where((e) => e.error != null).toList();

  if (failed.isEmpty && cancelled.isEmpty) {
    SmartDialog.showToast(
      succeeded.length == 1
          ? '已导出至 ${succeeded.single.location}'
          : '已导出 ${succeeded.length} 项',
    );
    return;
  }
  if (succeeded.isEmpty && failed.isEmpty) {
    SmartDialog.showToast('已取消导出');
    return;
  }

  final summary = StringBuffer();
  if (succeeded.isNotEmpty) summary.write('成功 ${succeeded.length} 项');
  if (failed.isNotEmpty) {
    if (summary.isNotEmpty) summary.write('，');
    summary.write('失败 ${failed.length} 项');
  }
  if (cancelled.isNotEmpty) {
    if (summary.isNotEmpty) summary.write('，');
    summary.write('取消 ${cancelled.length} 项');
  }

  final context = Get.context;
  if (context == null || failed.isEmpty) {
    SmartDialog.showToast(summary.toString());
    return;
  }
  showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(summary.toString()),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 8,
        children: [
          for (final item in failed)
            Text(
              '${item.mode.label}：${item.error}',
              style: const TextStyle(fontSize: 13),
            ),
        ],
      ),
      actions: [
        TextButton(onPressed: Get.back, child: const Text('确定')),
      ],
    ),
  );
}
