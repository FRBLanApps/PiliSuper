import 'dart:io' show Platform;

import 'package:PiliPlus/utils/android/bindings.g.dart';
import 'package:PiliPlus/utils/platform_utils.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart' show kDebugMode, debugPrint;
import 'package:flutter/widgets.dart' show WidgetsBinding, Size;

abstract final class DeviceUtils {
  static final int sdkInt = AndroidHelper.sdkInt();

  /// `PackageManager` 特性：TV 专用的 leanback UI 栈。
  static const String _featureLeanback = 'android.software.leanback';

  /// `PackageManager` 特性：设备类型为电视。
  static const String _featureTelevision = 'android.hardware.type.television';

  static bool _isTV = false;

  /// 当前设备是否为 Android TV。
  ///
  /// 判定结果由 [initTV] 在启动时解析并缓存。焦点高亮策略与主题构建都在同步
  /// 路径上读取该值，因此这里必须是同步 getter；在 [initTV] 完成前恒为 false。
  static bool get isTV => _isTV;

  /// 解析并缓存 TV 判定结果，必须在 `runApp` 之前 await 一次。
  ///
  /// 之所以走 `device_info_plus` 而非 JNI：本项目的 JNI 绑定
  /// (`lib/utils/android/bindings.g.dart`) 由 jnigen 生成且标注 DO NOT EDIT，
  /// 重新生成需要 Android SDK 与 Gradle 依赖解析。`systemFeatures` 透传的正是
  /// `PackageManager.getSystemAvailableFeatures`，信息等价且无需新增原生代码。
  static Future<void> initTV() async {
    if (!Platform.isAndroid) return;
    try {
      final features = (await DeviceInfoPlugin().androidInfo).systemFeatures;
      _isTV =
          features.contains(_featureLeanback) ||
          features.contains(_featureTelevision);
    } catch (e) {
      // 判定失败时保持 false，退化为现有的手机/平板行为。
      if (kDebugMode) debugPrint('TV detection failed: $e');
    }
  }

  static bool get isTablet {
    return size.shortestSide >= 600;
  }

  static Size get size {
    final view = WidgetsBinding.instance.platformDispatcher.views.first;
    return view.physicalSize / view.devicePixelRatio;
  }

  /// 注意：故意不为 TV 返回单独的值。该值参与设置备份文件名
  /// (`webdav.dart`、`about/view.dart`)，新增分支会让 TV 读不到既有备份。
  static String get platformName => PlatformUtils.isDesktop
      ? 'desktop'
      : isTablet
      ? 'pad'
      : 'phone';
}
