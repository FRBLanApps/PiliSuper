import 'package:PiliPlus/common/widgets/custom_icon.dart';
import 'package:PiliPlus/models/common/enum_with_label.dart';
import 'package:PiliPlus/pages/download/nav_bar_page.dart';
import 'package:PiliPlus/pages/dynamics/view.dart';
import 'package:PiliPlus/pages/fav/nav_bar_page.dart';
import 'package:PiliPlus/pages/home/view.dart';
import 'package:PiliPlus/pages/history/nav_bar_page.dart';
import 'package:PiliPlus/pages/later/nav_bar_page.dart';
import 'package:PiliPlus/pages/mine/view.dart';
import 'package:PiliPlus/pages/subscription/nav_bar_page.dart';
import 'package:flutter/material.dart';

enum NavigationBarType implements EnumWithLabel {
  home(
    '首页',
    Icon(Icons.home_outlined),
    Icon(Icons.home),
    HomePage(),
  ),
  dynamics(
    '动态',
    Icon(CustomIcons.motion_photos_on_outlined),
    Icon(CustomIcons.motion_photos_on),
    DynamicsPage(),
  ),
  mine(
    '我的',
    Icon(Icons.person_outline),
    Icon(Icons.person),
    MinePage(),
  ),
  history(
    '历史',
    Icon(Icons.history_outlined),
    Icon(Icons.history),
    HistoryNavBarPage(),
  ),
  fav(
    '收藏',
    Icon(CustomIcons.star_favorite_line),
    Icon(CustomIcons.star_favorite_solid),
    FavNavBarPage(),
  ),
  download(
    '缓存',
    Icon(CustomIcons.folderDownloadOutline),
    Icon(CustomIcons.folderDownloadOutline),
    DownloadNavBarPage(),
  ),
  subscription(
    '订阅',
    Icon(CustomIcons.subscriptions_outlined),
    Icon(CustomIcons.subscriptions_outlined),
    SubNavBarPage(),
  ),
  later(
    '稍后再看',
    Icon(CustomIcons.watch_later_outlined),
    Icon(CustomIcons.watch_later_outlined),
    LaterNavBarPage(),
  ),
  ;

  @override
  final String label;
  final Icon icon;
  final Icon selectIcon;
  final Widget page;

  const NavigationBarType(this.label, this.icon, this.selectIcon, this.page);
}
