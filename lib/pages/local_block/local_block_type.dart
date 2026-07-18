import 'package:PiliPlus/http/video.dart';
import 'package:PiliPlus/utils/ban_word_utils.dart';
import 'package:PiliPlus/utils/global_data.dart';
import 'package:PiliPlus/utils/recommend_filter.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:PiliPlus/utils/storage_key.dart';
import 'package:PiliPlus/utils/storage_pref.dart';

/// 本地屏蔽 / 视频过滤维度
enum LocalBlockType {
  up('UP'),
  title('标题'),
  zone('分区'),
  tag('TAG'),
  topic('话题'),
  desc('简介'),
  danmaku('弹幕'),
  rcmdType('稿件类型'),
  duration('时长');

  final String label;
  const LocalBlockType(this.label);

  bool get isUp => this == LocalBlockType.up;
  bool get isDanmaku => this == LocalBlockType.danmaku;
  bool get isRcmdType => this == LocalBlockType.rcmdType;
  bool get isDuration => this == LocalBlockType.duration;
  bool get isKeywordList =>
      this == LocalBlockType.title ||
      this == LocalBlockType.zone ||
      this == LocalBlockType.tag ||
      this == LocalBlockType.topic ||
      this == LocalBlockType.desc;

  String get storageKey => switch (this) {
    LocalBlockType.title => SettingBoxKey.banWordForRecommend,
    LocalBlockType.zone => SettingBoxKey.banWordForZone,
    LocalBlockType.tag => SettingBoxKey.banWordForTag,
    LocalBlockType.topic => SettingBoxKey.banWordForTopic,
    LocalBlockType.desc => SettingBoxKey.banWordForDesc,
    _ => '',
  };

  List<String> loadRules() {
    if (isUp) {
      return Pref.recommendBlockedMids.entries
          .map((e) => '${e.value} (${e.key})')
          .toList();
    }
    if (!isKeywordList) return [];
    final stored = GStorage.setting.get(storageKey, defaultValue: '') as String;
    return BanWordUtils.parseItems(stored);
  }

  void saveRules(List<String> items) {
    if (isUp) {
      final map = <int, String>{};
      for (final item in items) {
        final match = RegExp(r'^(.*)\s*\((\d+)\)$').firstMatch(item.trim());
        if (match != null) {
          final name = match.group(1)?.trim() ?? '';
          final uid = int.tryParse(match.group(2) ?? '');
          if (uid != null && uid > 0) {
            map[uid] = name.isEmpty ? 'UID:$uid' : name;
          }
        } else {
          final uid = int.tryParse(item.trim());
          if (uid != null && uid > 0) {
            map[uid] = 'UID:$uid';
          }
        }
      }
      Pref.recommendBlockedMids = map;
      GlobalData().recommendBlockedMids = map;
      RecommendFilter.recommendBlockedMids = map;
      return;
    }
    if (!isKeywordList) return;
    final stored = BanWordUtils.joinItems(items);
    GStorage.setting.put(storageKey, stored);
    applyRegExp(BanWordUtils.buildRegExp(stored));
  }

  void applyRegExp(RegExp re) {
    switch (this) {
      case LocalBlockType.title:
        RecommendFilter.rcmdRegExp = re;
        RecommendFilter.enableFilter = re.pattern.isNotEmpty;
        break;
      case LocalBlockType.zone:
        VideoHttp.zoneRegExp = re;
        VideoHttp.enableFilter = re.pattern.isNotEmpty;
        break;
      case LocalBlockType.tag:
        RecommendFilter.tagRegExp = re;
        RecommendFilter.enableTagFilter = re.pattern.isNotEmpty;
        break;
      case LocalBlockType.topic:
        RecommendFilter.topicRegExp = re;
        RecommendFilter.enableTopicFilter = re.pattern.isNotEmpty;
        break;
      case LocalBlockType.desc:
        RecommendFilter.descRegExp = re;
        RecommendFilter.enableDescFilter = re.pattern.isNotEmpty;
        break;
      default:
        break;
    }
  }

  void appendRule(String rule) {
    if (!isKeywordList) return;
    final stored = GStorage.setting.get(storageKey, defaultValue: '') as String;
    final next = BanWordUtils.appendRule(stored, rule);
    GStorage.setting.put(storageKey, next);
    applyRegExp(BanWordUtils.buildRegExp(next));
  }

  String get addHint => switch (this) {
    LocalBlockType.up => '输入用户 UID',
    LocalBlockType.title => '标题关键词或 /正则/flags',
    LocalBlockType.zone => '分区名或 /正则/flags',
    LocalBlockType.tag => 'TAG 或 /正则/flags',
    LocalBlockType.topic => '话题名或 /正则/flags',
    LocalBlockType.desc => '简介关键词或 /正则/flags',
    LocalBlockType.danmaku => '弹幕规则',
    LocalBlockType.rcmdType => '',
    LocalBlockType.duration => '',
  };
}

/// 可选屏蔽的推流稿件类型
enum RcmdBlockType {
  bangumi('bangumi', '番剧/影视'),
  picture('picture', '图文'),
  live('live', '直播'),
  liveRoom('live_room', '直播间'),
  ketang('ketang', '课堂'),
  special('special_s', '特殊卡片');

  final String goto;
  final String label;
  const RcmdBlockType(this.goto, this.label);
}
