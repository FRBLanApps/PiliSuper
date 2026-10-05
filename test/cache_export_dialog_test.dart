import 'dart:io';

import 'package:PiliPlus/models/common/export_mode.dart';
import 'package:PiliPlus/models_new/download/bili_download_entry_info.dart';
import 'package:PiliPlus/pages/download/detail/widgets/export_sheet.dart';
import 'package:PiliPlus/services/export/cache_export_service.dart';
import 'package:PiliPlus/utils/export/export_target.dart';
import 'package:PiliPlus/utils/path_utils.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:get/get.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory cacheDir;
  late Directory exportDir;

  setUp(() async {
    cacheDir = await Directory.systemTemp.createTemp('pili_cache_');
    exportDir = await Directory.systemTemp.createTemp('pili_export_');
    await File(
      '${cacheDir.path}${Platform.pathSeparator}${PathUtils.coverName}',
    ).writeAsBytes([0xFF, 0xD8, 0xFF]);
    await setExportTarget(FsTarget(exportDir.path));
    Get.testMode = true;
  });

  tearDown(() {
    Get
      ..deleteAll(force: true)
      ..reset();
    if (cacheDir.existsSync()) cacheDir.deleteSync(recursive: true);
    if (exportDir.existsSync()) exportDir.deleteSync(recursive: true);
  });

  BiliDownloadEntryInfo entry() => BiliDownloadEntryInfo(
    isCompleted: true,
    totalBytes: 1,
    downloadedBytes: 1,
    title: '缓存条目',
    cover: '',
    preferedVideoQuality: 80,
    guessedTotalBytes: 1,
    totalTimeMilli: 1000,
    danmakuCount: 0,
    avid: 1,
    bvid: 'BV1',
  )..entryDirPath = cacheDir.path;

  CheckboxListTile tile(WidgetTester tester, String label) {
    return tester.widget<CheckboxListTile>(
      find.widgetWithText(CheckboxListTile, label),
    );
  }

  testWidgets('options dialog opens, toggles selection, and dismisses', (
    tester,
  ) async {
    await tester.pumpWidget(_host(entry()));
    await tester.tap(find.text('打开导出'));
    await tester.pumpAndSettle();

    expect(find.text('导出缓存'), findsOneWidget);
    expect(tile(tester, '整体导出(MKV)').value, isTrue);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('整体导出(MKV)'));
    await tester.pumpAndSettle();
    expect(tile(tester, '整体导出(MKV)').value, isFalse);
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, '开始导出'))
          .onPressed,
      isNull,
    );

    await tester.tap(find.text('视频'));
    await tester.pumpAndSettle();
    expect(tile(tester, '视频').value, isTrue);
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, '开始导出'))
          .onPressed,
      isNotNull,
    );

    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
    expect(find.text('导出缓存'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('progress dialog renders from a fake export service', (
    tester,
  ) async {
    final service = _FakeExportService()
      ..stage.value = ExportStage.video
      ..currentLabel.value = '视频'
      ..progress.value = 0.4;

    await tester.pumpWidget(_host(entry()));
    showExportProgressDialog(service);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('正在导出'), findsOneWidget);
    expect(find.textContaining('导出视频'), findsOneWidget);
    expect(find.text('40.0%'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(tester.takeException(), isNull);

    service.progress.value = 0.75;
    await tester.pump();
    expect(find.text('75.0%'), findsOneWidget);
    expect(find.text('40.0%'), findsNothing);

    await tester.tap(find.text('后台运行'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('正在导出'), findsNothing);
    expect(service.exportCalls, 0);

    await tester.pump(const Duration(seconds: 3));
    await SmartDialog.dismiss(status: SmartStatus.toast);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('failed export summary shows the error without native export', (
    tester,
  ) async {
    final service = _FakeExportService()
      ..results = const [
        ExportItemResult.failure(ExportMode.video, '转封装失败'),
      ];
    Get.lazyPut<CacheExportService>(() => service);

    await tester.pumpWidget(_host(entry()));
    await tester.tap(find.text('打开导出'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('开始导出'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(service.exportCalls, 1);
    expect(find.textContaining('失败 1 项'), findsOneWidget);
    expect(find.textContaining('转封装失败'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('确定'));
    await tester.pumpAndSettle();
    expect(find.textContaining('转封装失败'), findsNothing);
  });
}

Widget _host(BiliDownloadEntryInfo entry) {
  return GetMaterialApp(
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    locale: const Locale('zh', 'CN'),
    supportedLocales: const [Locale('zh', 'CN'), Locale('en', 'US')],
    builder: FlutterSmartDialog.init(),
    navigatorObservers: [FlutterSmartDialog.observer],
    home: Scaffold(
      body: Builder(
        builder: (context) => TextButton(
          onPressed: () => showExportSheet(context: context, entry: entry),
          child: const Text('打开导出'),
        ),
      ),
    ),
  );
}

class _FakeExportService extends CacheExportService {
  List<ExportItemResult> results = const [];
  int exportCalls = 0;

  @override
  Future<List<ExportItemResult>> export({
    required BiliDownloadEntryInfo entry,
    required Set<ExportMode> modes,
  }) async {
    exportCalls++;
    return results;
  }
}
