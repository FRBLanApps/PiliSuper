import 'package:PiliPlus/models/model_video.dart';
import 'package:PiliPlus/utils/ban_word_utils.dart';
import 'package:PiliPlus/utils/storage_pref.dart';

/// 过滤器作用范围
enum FilterScope {
  /// 首页推荐（始终应用）
  rcmd,

  /// 详情相关视频
  related,

  /// 热门
  hot,

  /// 分区/排行
  rank,

  /// 搜索（仅标题 + 屏蔽 UP）
  search,
}

abstract final class RecommendFilter {
  static int minDurationForRcmd = Pref.minDurationForRcmd;
  static int minPlayForRcmd = Pref.minPlayForRcmd;
  static int minLikeRatioForRecommend = Pref.minLikeRatioForRecommend;
  static bool exemptFilterForFollowed = Pref.exemptFilterForFollowed;
  static bool applyFilterToRelatedVideos = Pref.applyFilterToRelatedVideos;
  static bool applyFilterToHotVideos = Pref.applyFilterToHotVideos;
  static bool applyFilterToRankVideos = Pref.applyFilterToRankVideos;
  static bool applyFilterToSearch = Pref.applyFilterToSearch;

  static RegExp rcmdRegExp = BanWordUtils.buildRegExp(Pref.banWordForRecommend);
  static bool enableFilter = rcmdRegExp.pattern.isNotEmpty;

  static RegExp descRegExp = BanWordUtils.buildRegExp(Pref.banWordForDesc);
  static bool enableDescFilter = descRegExp.pattern.isNotEmpty;

  static RegExp tagRegExp = BanWordUtils.buildRegExp(Pref.banWordForTag);
  static bool enableTagFilter = tagRegExp.pattern.isNotEmpty;

  static RegExp topicRegExp = BanWordUtils.buildRegExp(Pref.banWordForTopic);
  static bool enableTopicFilter = topicRegExp.pattern.isNotEmpty;

  static Map<int, String> recommendBlockedMids = Pref.recommendBlockedMids;
  static Set<String> blockedRcmdTypes = Pref.blockedRcmdTypes;

  static bool isScopeEnabled(FilterScope scope) => switch (scope) {
    FilterScope.rcmd => true,
    FilterScope.related => applyFilterToRelatedVideos,
    FilterScope.hot => applyFilterToHotVideos,
    FilterScope.rank => applyFilterToRankVideos,
    FilterScope.search => applyFilterToSearch,
  };

  static bool filterUser(int? mid) {
    return recommendBlockedMids.isNotEmpty &&
        mid != null &&
        mid > 0 &&
        recommendBlockedMids.containsKey(mid);
  }

  /// 推流稿件类型是否应屏蔽（goto / card_goto）
  static bool filterRcmdType(String? goto) {
    if (goto == null || goto.isEmpty || blockedRcmdTypes.isEmpty) {
      return false;
    }
    return blockedRcmdTypes.contains(goto);
  }

  static bool filterLikeRatio(int? like, int? view) {
    if (view != null) {
      return (view > -1 && view < minPlayForRcmd) ||
          (like != null &&
              like > -1 &&
              like * 100 < minLikeRatioForRecommend * view);
    }
    return false;
  }

  static bool filterTitle(String title) {
    return enableFilter && rcmdRegExp.hasMatch(title);
  }

  static bool filterDesc(String? desc) {
    if (!enableDescFilter || desc == null || desc.isEmpty) return false;
    return descRegExp.hasMatch(desc);
  }

  static bool filterTags(Iterable<String>? tags) {
    if (!enableTagFilter || tags == null) return false;
    for (final t in tags) {
      if (t.isNotEmpty && tagRegExp.hasMatch(t)) return true;
    }
    return false;
  }

  static bool filterTopics(Iterable<String>? topics) {
    if (!enableTopicFilter || topics == null) return false;
    for (final t in topics) {
      if (t.isNotEmpty && topicRegExp.hasMatch(t)) return true;
    }
    return false;
  }

  /// 搜索：仅标题 + 本地屏蔽 UP
  static bool filterForSearch({int? mid, required String title}) {
    if (!applyFilterToSearch) return false;
    if (filterUser(mid)) return true;
    return filterTitle(title);
  }

  /// 完整过滤（推荐/热门/排行/相关）。返回 true 表示应丢弃。
  ///
  /// 注意：本地屏蔽 UP 始终生效（不受作用域关闭影响），
  /// 作用域关闭时仅跳过关键词/阈值等规则。
  static bool filter(
    BaseVideoItemModel videoItem, {
    FilterScope scope = FilterScope.rcmd,
  }) {
    // 本地屏蔽 UP：各作用域均生效
    if (filterUser(videoItem.owner.mid)) {
      return true;
    }

    if (!isScopeEnabled(scope)) return false;

    // 搜索：仅标题（UP 已在上方处理）
    if (scope == FilterScope.search) {
      return filterTitle(videoItem.title);
    }

    if (videoItem.isFollowed && exemptFilterForFollowed) {
      return false;
    }
    return filterAll(videoItem);
  }

  /// 不含 mid 重复检查（由 filter 入口统一处理）
  static bool filterAll(BaseVideoItemModel videoItem) {
    return (videoItem.duration > 0 &&
            videoItem.duration < minDurationForRcmd) ||
        filterLikeRatio(videoItem.stat.like, videoItem.stat.view) ||
        filterTitle(videoItem.title) ||
        filterDesc(videoItem.desc) ||
        filterTags(videoItem.tagNames) ||
        filterTopics(videoItem.topicNames);
  }

  /// 仅 TAG/话题（预加载完成后二次过滤用）
  static bool filterByMeta(BaseVideoItemModel videoItem) {
    if (filterUser(videoItem.owner.mid)) return true;
    if (videoItem.isFollowed && exemptFilterForFollowed) return false;
    return filterTags(videoItem.tagNames) || filterTopics(videoItem.topicNames);
  }
}
