import 'package:PiliPlus/pages/setting/models/model.dart';
import 'package:PiliPlus/utils/recommend_filter.dart';
import 'package:PiliPlus/utils/storage_key.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

List<SettingsModel> get filterSettings => [
  NormalModel(
    title: '视频过滤',
    leading: const Icon(Icons.block_outlined),
    subtitle: 'UP / 标题 / 分区 / TAG / 话题 / 简介 / 弹幕 / 稿件类型；作用域与时长在页内设置',
    onTap: (context, setState) => Get.toNamed('/localBlock'),
  ),
  getVideoFilterSelectModel(
    title: '点赞率',
    suffix: '%',
    key: SettingBoxKey.minLikeRatioForRecommend,
    values: [0, 1, 2, 3, 4],
    onChanged: (value) => RecommendFilter.minLikeRatioForRecommend = value,
  ),
  getVideoFilterSelectModel(
    title: '浏览量',
    key: SettingBoxKey.minPlayForRcmd,
    values: [0, 50, 100, 500, 1000],
    onChanged: (value) => RecommendFilter.minPlayForRcmd = value,
  ),
  SwitchModel(
    title: '已关注 UP 豁免',
    subtitle: '推荐中已关注用户发布的内容不会被过滤（本地屏蔽 UP 仍生效）',
    leading: const Icon(Icons.favorite_border_outlined),
    setKey: SettingBoxKey.exemptFilterForFollowed,
    defaultVal: true,
    onChanged: (value) => RecommendFilter.exemptFilterForFollowed = value,
  ),
];
