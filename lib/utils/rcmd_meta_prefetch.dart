import 'dart:async';

import 'package:PiliPlus/http/user.dart';
import 'package:PiliPlus/models/model_video.dart';
import 'package:PiliPlus/models_new/video/video_tag/data.dart';
import 'package:PiliPlus/utils/recommend_filter.dart';
import 'package:flutter/foundation.dart' show kDebugMode, debugPrint;

/// 首页 feed 元数据预加载：TAG / 话题
///
/// 限流并发请求，避免一刷 20 条打爆 tag API。
abstract final class RcmdMetaPrefetch {
  static const _maxConcurrent = 3;
  static const _timeout = Duration(seconds: 4);

  /// 为列表项预取 tags；返回因 TAG/话题规则应移除的 bvid 集合
  static Future<Set<String>> prefetchAndCollectBlocked(
    List items, {
    bool Function()? isCancelled,
  }) async {
    if (!RecommendFilter.enableTagFilter &&
        !RecommendFilter.enableTopicFilter) {
      // 无规则时仍预取元数据供快捷屏蔽（低优先级，限制数量）
      unawaited(_prefetchOnly(items.take(8).toList()));
      return {};
    }

    final candidates = <BaseVideoItemModel>[];
    for (final e in items) {
      if (e is! BaseVideoItemModel) continue;
      if (e.bvid == null || e.bvid!.isEmpty) continue;
      if (e.tagNames != null || e.topicNames != null) continue; // 已加载
      candidates.add(e);
    }
    if (candidates.isEmpty) return {};

    final blocked = <String>{};
    var index = 0;

    Future<void> worker() async {
      while (index < candidates.length) {
        if (isCancelled?.call() == true) return;
        final i = index++;
        if (i >= candidates.length) return;
        final item = candidates[i];
        try {
          await _fillTags(item).timeout(_timeout);
          if (RecommendFilter.filterByMeta(item) && item.bvid != null) {
            blocked.add(item.bvid!);
          }
        } catch (e) {
          if (kDebugMode) debugPrint('rcmd meta prefetch: $e');
        }
      }
    }

    final n = candidates.length < _maxConcurrent
        ? candidates.length
        : _maxConcurrent;
    await Future.wait(List.generate(n, (_) => worker()));
    return blocked;
  }

  static Future<void> _prefetchOnly(List items) async {
    for (final e in items) {
      if (e is! BaseVideoItemModel) continue;
      if (e.bvid == null || e.tagNames != null) continue;
      try {
        await _fillTags(e).timeout(_timeout);
      } catch (_) {}
    }
  }

  static Future<void> _fillTags(BaseVideoItemModel item) async {
    final res = await UserHttp.videoTags(bvid: item.bvid!, cid: item.cid);
    final tags = res.dataOrNull;
    final tagNames = <String>[];
    final topicNames = <String>[];
    for (final t in tags ?? const <VideoTagItem>[]) {
      final name = t.tagName?.trim();
      if (name == null || name.isEmpty) continue;
      if (t.tagType == 'topic') {
        topicNames.add(name);
      } else if (t.tagType != 'bgm') {
        tagNames.add(name);
      }
    }
    item.tagNames = tagNames;
    item.topicNames = topicNames;
  }
}
