import 'dart:io';

import 'package:PiliSuper/build_config.dart';
import 'package:PiliSuper/common/constants.dart';
import 'package:PiliSuper/common/widgets/custom_toast.dart';
import 'package:PiliSuper/common/widgets/mouse_back.dart';
import 'package:PiliSuper/http/init.dart';
import 'package:PiliSuper/models/common/theme/theme_color_type.dart';
import 'package:PiliSuper/plugin/pl_player/controller.dart';
import 'package:PiliSuper/router/app_pages.dart';
import 'package:PiliSuper/services/account_service.dart';
import 'package:PiliSuper/services/download/download_service.dart';
import 'package:PiliSuper/services/service_locator.dart';
import 'package:PiliSuper/utils/app_scheme.dart';
import 'package:PiliSuper/utils/cache_manager.dart';
import 'package:PiliSuper/utils/calc_window_position.dart';
import 'package:PiliSuper/utils/date_utils.dart';
import 'package:PiliSuper/utils/json_file_handler.dart';
import 'package:PiliSuper/utils/page_utils.dart';
import 'package:PiliSuper/utils/path_utils.dart';
import 'package:PiliSuper/utils/request_utils.dart';
import 'package:PiliSuper/utils/storage.dart';
import 'package:PiliSuper/utils/storage_key.dart';
import 'package:PiliSuper/utils/storage_pref.dart';
import 'package:PiliSuper/utils/theme_utils.dart';
import 'package:PiliSuper/utils/utils.dart';
import 'package:catcher_2/catcher_2.dart';
import 'package:dynamic_color/dynamic_color.dart';
import 'package:flex_seed_scheme/flex_seed_scheme.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart' show PointerDeviceKind;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_displaymode/flutter_displaymode.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';
import 'package:media_kit/media_kit.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:window_manager/window_manager.dart' hide calcWindowPosition;

WebViewEnvironment? webViewEnvironment;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();
  tmpDirPath = (await getTemporaryDirectory()).path;
  appSupportDirPath = (await getApplicationSupportDirectory()).path;
  try {
    await GStorage.init();
  } catch (e) {
    await Utils.copyText(e.toString());
    if (kDebugMode) debugPrint('GStorage init error: $e');
    exit(0);
  }
  if (Utils.isDesktop) {
    final customDownPath = Pref.downloadPath;
    if (customDownPath != null && customDownPath.isNotEmpty) {
      try {
        final dir = Directory(customDownPath);
        if (!dir.existsSync()) {
          await dir.create(recursive: true);
        }
        downloadPath = customDownPath;
      } catch (e) {
        downloadPath = defDownloadPath;
        await GStorage.setting.delete(SettingBoxKey.downloadPath);
        if (kDebugMode) {
          debugPrint('download path error: $e');
        }
      }
    } else {
      downloadPath = defDownloadPath;
    }
  } else if (Platform.isAndroid) {
    final externalStorageDirPath = (await getExternalStorageDirectory())?.path;
    downloadPath = externalStorageDirPath != null
        ? path.join(externalStorageDirPath, PathUtils.downloadDir)
        : defDownloadPath;
  } else {
    downloadPath = defDownloadPath;
  }
  Get
    ..lazyPut(AccountService.new)
    ..lazyPut(DownloadService.new);
  HttpOverrides.global = _CustomHttpOverrides();

  CacheManager.autoClearCache();

  if (Utils.isMobile) {
    await Future.wait([
      SystemChrome.setPreferredOrientations(
        [
          DeviceOrientation.portraitUp,
          if (Pref.horizontalScreen) ...[
            DeviceOrientation.landscapeLeft,
            DeviceOrientation.landscapeRight,
          ],
        ],
      ),
      setupServiceLocator(),
    ]);
  }

  if (Platform.isWindows) {
    if (await WebViewEnvironment.getAvailableVersion() != null) {
      webViewEnvironment = await WebViewEnvironment.create(
        settings: WebViewEnvironmentSettings(
          userDataFolder: path.join(appSupportDirPath, 'flutter_inappwebview'),
        ),
      );
    }
  }

  Request();
  Request.setCookie();
  RequestUtils.syncHistoryStatus();

  SmartDialog.config.toast = SmartConfigToast(
    displayType: SmartToastType.onlyRefresh,
  );

  if (Utils.isMobile) {
    PiliScheme.init();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        systemNavigationBarColor: Colors.transparent,
        systemNavigationBarDividerColor: Colors.transparent,
        statusBarColor: Colors.transparent,
        systemNavigationBarContrastEnforced: false,
      ),
    );
    if (Platform.isAndroid) {
      late List<DisplayMode> modes;
      FlutterDisplayMode.supported.then((value) {
        modes = value;
        final String? storageDisplay = GStorage.setting.get(
          SettingBoxKey.displayMode,
        );
        DisplayMode? displayMode;
        if (storageDisplay != null) {
          displayMode = modes.firstWhereOrNull(
            (e) => e.toString() == storageDisplay,
          );
        }
        FlutterDisplayMode.setPreferredMode(displayMode ?? DisplayMode.auto);
      });
    }
  } else if (Utils.isDesktop) {
    await windowManager.ensureInitialized();

    WindowOptions windowOptions = WindowOptions(
      minimumSize: const Size(400, 720),
      skipTaskbar: false,
      titleBarStyle: Pref.showWindowTitleBar
          ? TitleBarStyle.normal
          : TitleBarStyle.hidden,
      title: Constants.appName,
    );
    windowManager.waitUntilReadyToShow(windowOptions, () async {
      final windowSize = Pref.windowSize;
      await windowManager.setBounds(
        await calcWindowPosition(windowSize) & windowSize,
      );
      if (Pref.isWindowMaximized) await windowManager.maximize();
      await windowManager.show();
      await windowManager.focus();
    });
  }

  if (Pref.enableLog) {
    // 异常捕获 logo记录
    final customParameters = {
      'BuildConfig':
          '\nBuild Time: ${DateFormatUtils.format(BuildConfig.buildTime, format: DateFormatUtils.longFormatDs)}\n'
          'Commit Hash: ${BuildConfig.commitHash}',
    };
    final fileHandler = await JsonFileHandler.init();
    final Catcher2Options debugConfig = Catcher2Options(
      SilentReportMode(),
      [
        ?fileHandler,
        ConsoleHandler(
          enableDeviceParameters: false,
          enableApplicationParameters: false,
          enableCustomParameters: true,
        ),
      ],
      customParameters: customParameters,
    );

    final Catcher2Options releaseConfig = Catcher2Options(
      SilentReportMode(),
      [
        ?fileHandler,
        ConsoleHandler(enableCustomParameters: true),
      ],
      customParameters: customParameters,
    );

    Catcher2(
      debugConfig: debugConfig,
      releaseConfig: releaseConfig,
      rootWidget: const MyApp(),
    );
  } else {
    runApp(const MyApp());
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  static ThemeData? darkThemeData;

  static void _onBack() {
    if (SmartDialog.checkExist()) {
      SmartDialog.dismiss();
      return;
    }

    if (Get.isDialogOpen ?? Get.isBottomSheetOpen ?? false) {
      Get.back();
      return;
    }

    final plCtr = PlPlayerController.instance;
    if (plCtr != null) {
      if (plCtr.isFullScreen.value) {
        plCtr
          ..triggerFullScreen(status: false)
          ..controlsLock.value = false
          ..showControls.value = false;
        return;
      }

      if (plCtr.isDesktopPip) {
        plCtr
          ..exitDesktopPip().whenComplete(
            () => plCtr.initialFocalPoint = Offset.zero,
          )
          ..controlsLock.value = false
          ..showControls.value = false;
        return;
      }
    }

    Get.back();
  }

  static Widget _build({
    ColorScheme? lightColorScheme,
    ColorScheme? darkColorScheme,
  }) {
    late final brandColor = colorThemeTypes[Pref.customColor].color;
    late final variant = FlexSchemeVariant.values[Pref.schemeVariant];
    return GetMaterialApp(
      title: Constants.appName,
      theme: ThemeUtils.getThemeData(
        colorScheme:
            lightColorScheme ??
            SeedColorScheme.fromSeeds(
              variant: variant,
              primaryKey: brandColor,
              brightness: Brightness.light,
              useExpressiveOnContainerColors: false,
            ),
        isDynamic: lightColorScheme != null,
      ),
      darkTheme: ThemeUtils.getThemeData(
        isDark: true,
        colorScheme:
            darkColorScheme ??
            SeedColorScheme.fromSeeds(
              variant: variant,
              primaryKey: brandColor,
              brightness: Brightness.dark,
              useExpressiveOnContainerColors: false,
            ),
        isDynamic: darkColorScheme != null,
      ),
      themeMode: Pref.themeMode,
      localizationsDelegates: const [
        GlobalCupertinoLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ],
      locale: const Locale("zh", "CN"),
      fallbackLocale: const Locale("zh", "CN"),
      supportedLocales: const [Locale("zh", "CN"), Locale("en", "US")],
      initialRoute: '/',
      getPages: Routes.getPages,
      defaultTransition: Pref.pageTransition,
      builder: FlutterSmartDialog.init(
        toastBuilder: (String msg) => CustomToast(msg: msg),
        loadingBuilder: (msg) => LoadingWidget(msg: msg),
        builder: (context, child) {
          child = MediaQuery(
            data: MediaQuery.of(context).copyWith(
              textScaler: TextScaler.linear(Pref.defaultTextScale),
            ),
            child: child!,
          );
          if (Utils.isDesktop) {
            return Focus(
              canRequestFocus: false,
              onKeyEvent: (_, event) {
                if (event.logicalKey == LogicalKeyboardKey.escape &&
                    event is KeyDownEvent) {
                  _onBack();
                  return KeyEventResult.handled;
                }
                return KeyEventResult.ignored;
              },
              child: MouseBackDetector(
                onTapDown: _onBack,
                child: child,
              ),
            );
          }
          return child;
        },
      ),
      navigatorObservers: [
        PageUtils.routeObserver,
        FlutterSmartDialog.observer,
      ],
      scrollBehavior: const MaterialScrollBehavior().copyWith(
        scrollbars: false,
        dragDevices: {
          PointerDeviceKind.touch,
          PointerDeviceKind.stylus,
          PointerDeviceKind.invertedStylus,
          PointerDeviceKind.trackpad,
          PointerDeviceKind.unknown,
          if (Utils.isDesktop) PointerDeviceKind.mouse,
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!Platform.isIOS && Pref.dynamicColor) {
      return DynamicColorBuilder(
        builder: ((ColorScheme? lightDynamic, ColorScheme? darkDynamic) {
          if (lightDynamic != null && darkDynamic != null) {
            return _build(
              lightColorScheme: lightDynamic.harmonized(),
              darkColorScheme: darkDynamic.harmonized(),
            );
          } else {
            return _build();
          }
        }),
      );
    }
    return _build();
  }
}

class _CustomHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    final client = super.createHttpClient(context)
      // ..maxConnectionsPerHost = 32
      ..idleTimeout = const Duration(seconds: 15);
    if (kDebugMode || Pref.badCertificateCallback) {
      client.badCertificateCallback = (cert, host, port) => true;
    }
    return client;
  }
}
