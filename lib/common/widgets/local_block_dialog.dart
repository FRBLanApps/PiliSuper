import 'package:PiliPlus/common/widgets/dialog/dialog.dart';
import 'package:PiliPlus/http/user.dart';
import 'package:PiliPlus/models_new/video/video_tag/data.dart';
import 'package:PiliPlus/pages/local_block/local_block_type.dart';
import 'package:PiliPlus/utils/global_data.dart';
import 'package:PiliPlus/utils/recommend_filter.dart';
import 'package:PiliPlus/utils/storage_pref.dart';
import 'package:PiliPlus/utils/utils.dart';
import 'package:flutter/material.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';

/// 快捷本地屏蔽：打开时可选预取 TAG/话题 API
class LocalBlockDialog {
  LocalBlockDialog._();

  static Future<void> show({
    required BuildContext context,
    String? bvid,
    Object? cid,
    String? ownerName,
    int? ownerMid,
    String? title,
    String? zoneName,
    String? desc,
    List<VideoTagItem>? initialTags,
    List<String>? preloadedTagNames,
    List<String>? preloadedTopicNames,
    VoidCallback? onBlocked,
  }) async {
    // 优先用调用方传入的预加载 meta；否则请求 API
    List<String> tagNames = [];
    List<String> topicNames = [];
    if (preloadedTagNames != null || preloadedTopicNames != null) {
      tagNames = List<String>.from(preloadedTagNames ?? const []);
      topicNames = List<String>.from(preloadedTopicNames ?? const []);
    } else {
      List<VideoTagItem>? tags = initialTags;
      if ((tags == null || tags.isEmpty) && bvid != null && bvid.isNotEmpty) {
        SmartDialog.showLoading(msg: '加载标签…');
        try {
          final res = await UserHttp.videoTags(bvid: bvid, cid: cid);
          tags = res.dataOrNull;
        } catch (_) {}
        SmartDialog.dismiss();
      }
      for (final t in tags ?? const <VideoTagItem>[]) {
        final name = t.tagName?.trim();
        if (name == null || name.isEmpty) continue;
        if (t.tagType == 'topic') {
          topicNames.add(name);
        } else if (t.tagType != 'bgm') {
          tagNames.add(name);
        }
      }
    }

    if (!context.mounted) return;

    final colorScheme = Theme.of(context).colorScheme;

    Widget chip(String label, {VoidCallback? onTap, bool enabled = true}) {
      final bg = enabled
          ? colorScheme.onInverseSurface
          : colorScheme.surfaceContainerHighest.withValues(alpha: 0.5);
      final fg = enabled
          ? colorScheme.onSurfaceVariant
          : colorScheme.outline.withValues(alpha: 0.6);
      return Material(
        color: bg,
        borderRadius: const BorderRadius.all(Radius.circular(6)),
        child: InkWell(
          borderRadius: const BorderRadius.all(Radius.circular(6)),
          onTap: enabled ? onTap : null,
          onLongPress: enabled ? () => Utils.copyText(label) : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
            child: Text(
              label,
              style: TextStyle(color: fg),
            ),
          ),
        ),
      );
    }

    Future<void> addUp() async {
      // mid==0 多为缺省值，不能当作有效 UP
      if (ownerMid == null || ownerMid <= 0) {
        SmartDialog.showToast('无法获取用户ID');
        return;
      }
      if (!context.mounted) return;
      final name = (ownerName?.trim().isNotEmpty == true)
          ? ownerName!.trim()
          : 'UID:$ownerMid';
      final ok = await showConfirmDialog(
        context: context,
        title: const Text('确认本地屏蔽 UP'),
        content: Text('$name ($ownerMid)'),
      );
      if (!ok) return;
      final blockedMids = Map<int, String>.from(Pref.recommendBlockedMids);
      if (blockedMids.containsKey(ownerMid)) {
        SmartDialog.showToast('该 UP 已在本地屏蔽列表中');
        onBlocked?.call();
        return;
      }
      blockedMids[ownerMid] = name;
      Pref.recommendBlockedMids = blockedMids;
      GlobalData().recommendBlockedMids = blockedMids;
      RecommendFilter.recommendBlockedMids = blockedMids;
      SmartDialog.showToast('已本地屏蔽 $name($ownerMid)');
      onBlocked?.call();
    }

    Future<void> appendKeyword({
      required LocalBlockType type,
      required String value,
      required String successMsg,
    }) async {
      final keyword = value.trim();
      if (keyword.isEmpty) {
        SmartDialog.showToast('内容为空');
        return;
      }
      final existing = type.loadRules();
      if (existing.contains(keyword)) {
        SmartDialog.showToast('已存在该屏蔽规则');
        // 已屏蔽：仍回调以便列表移除该卡片，但不重复写入
        onBlocked?.call();
        return;
      }
      if (!context.mounted) return;
      final ok = await showConfirmDialog(
        context: context,
        title: Text('确认加入${type.label}屏蔽'),
        content: Text(keyword),
      );
      if (!ok) return;
      type.appendRule(keyword);
      SmartDialog.showToast(successMsg);
      onBlocked?.call();
    }

    Future<void> showCustom() async {
      if (!context.mounted) return;
      LocalBlockType selected = LocalBlockType.title;
      final ctr = TextEditingController();
      final result = await showDialog<(LocalBlockType, String)>(
        context: context,
        builder: (context) {
          return StatefulBuilder(
            builder: (context, setState) {
              return AlertDialog(
                title: const Text('自定义屏蔽'),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButtonFormField<LocalBlockType>(
                      value: selected,
                      items: [
                        for (final t in LocalBlockType.values)
                          if (!t.isUp)
                            DropdownMenuItem(value: t, child: Text(t.label)),
                      ],
                      onChanged: (v) {
                        if (v != null) setState(() => selected = v);
                      },
                      decoration: const InputDecoration(labelText: '屏蔽类型'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: ctr,
                      autofocus: true,
                      decoration: InputDecoration(
                        hintText: selected.addHint,
                        labelText: '规则（普通文字或 /正则/flags）',
                      ),
                      maxLines: 3,
                    ),
                  ],
                ),
                actions: [
                  TextButton(onPressed: Get.back, child: const Text('取消')),
                  TextButton(
                    onPressed: () =>
                        Get.back(result: (selected, ctr.text.trim())),
                    child: const Text('下一步'),
                  ),
                ],
              );
            },
          );
        },
      );
      ctr.dispose();
      if (result == null) return;
      final (type, text) = result;
      if (text.isEmpty) {
        SmartDialog.showToast('内容为空');
        return;
      }
      await appendKeyword(
        type: type,
        value: text,
        successMsg: '已加入${type.label}屏蔽',
      );
    }

    final titleTrim = title?.trim() ?? '';
    final zoneTrim = zoneName?.trim();
    final descTrim = desc?.trim();

    await showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('本地屏蔽'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '快捷选项（长按复制）',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    chip(
                      (ownerMid != null && ownerMid > 0)
                          ? 'UP主:${(ownerName?.trim().isNotEmpty == true) ? ownerName!.trim() : ownerMid}'
                          : 'UP主:无法获取',
                      enabled: ownerMid != null && ownerMid > 0,
                      onTap: () {
                        Get.back();
                        addUp();
                      },
                    ),
                    chip(
                      titleTrim.isNotEmpty ? '标题:$titleTrim' : '标题:无法获取',
                      enabled: titleTrim.isNotEmpty,
                      onTap: () {
                        Get.back();
                        appendKeyword(
                          type: LocalBlockType.title,
                          value: titleTrim,
                          successMsg: '已加入标题关键词屏蔽',
                        );
                      },
                    ),
                    chip(
                      zoneTrim?.isNotEmpty == true
                          ? '分区:$zoneTrim'
                          : '分区:无法获取',
                      enabled: zoneTrim?.isNotEmpty == true,
                      onTap: () {
                        Get.back();
                        appendKeyword(
                          type: LocalBlockType.zone,
                          value: zoneTrim!,
                          successMsg: '已加入分区关键词屏蔽',
                        );
                      },
                    ),
                    chip(
                      descTrim != null && descTrim.isNotEmpty
                          ? '简介:${descTrim.length > 40 ? '${descTrim.substring(0, 40)}…' : descTrim}'
                          : '简介:无法获取',
                      enabled: descTrim != null && descTrim.isNotEmpty,
                      onTap: () {
                        Get.back();
                        appendKeyword(
                          type: LocalBlockType.desc,
                          value: descTrim!,
                          successMsg: '已加入简介屏蔽',
                        );
                      },
                    ),
                    if (tagNames.isEmpty)
                      chip('TAG:无法获取', enabled: false)
                    else
                      for (final t in tagNames)
                        chip(
                          'TAG:$t',
                          onTap: () {
                            Get.back();
                            appendKeyword(
                              type: LocalBlockType.tag,
                              value: t,
                              successMsg: '已加入 TAG 屏蔽',
                            );
                          },
                        ),
                    if (topicNames.isEmpty)
                      chip('话题:无法获取', enabled: false)
                    else
                      for (final t in topicNames)
                        chip(
                          '话题:$t',
                          onTap: () {
                            Get.back();
                            appendKeyword(
                              type: LocalBlockType.topic,
                              value: t,
                              successMsg: '已加入话题屏蔽',
                            );
                          },
                        ),
                    chip(
                      '自定义…',
                      onTap: () {
                        Get.back();
                        showCustom();
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Get.back();
                Get.toNamed('/localBlock');
              },
              child: const Text('管理'),
            ),
            TextButton(onPressed: Get.back, child: const Text('取消')),
          ],
        );
      },
    );
  }
}
