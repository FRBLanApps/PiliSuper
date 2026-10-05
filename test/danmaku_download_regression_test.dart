import 'dart:io';
import 'dart:typed_data';

import 'package:PiliPlus/grpc/bilibili/community/service/dm/v1.pb.dart';
import 'package:PiliPlus/grpc/grpc_req.dart';
import 'package:PiliPlus/http/init.dart';
import 'package:PiliPlus/models_new/download/bili_download_entry_info.dart';
import 'package:PiliPlus/services/download/download_service.dart';
import 'package:PiliPlus/utils/danmaku_utils.dart';
import 'package:PiliPlus/utils/path_utils.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:dio/dio.dart' as dio;
import 'package:dio/io.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  late Directory temp;
  late dio.Interceptor interceptor;
  setUpAll(() async {
    temp = await Directory.systemTemp.createTemp('dm-regression');
    Hive.init(temp.path);
    GStorage.setting = await Hive.openBox('setting');
    GStorage.video = await Hive.openBox('video');
    GStorage.localCache = await Hive.openBox('localCache');
    await GStorage.setting.put('retryCount', 0);
    Request();
    Request.dio
      ..interceptors.clear()
      ..httpClientAdapter = IOHttpClientAdapter();
  });
  tearDownAll(() async {
    Request.dio.interceptors.remove(interceptor);
    Request.dio.close(force: true);
    await GStorage.setting.close();
    await GStorage.video.close();
    await GStorage.localCache.close();
    await temp.delete(recursive: true);
  });

  void installFake({bool initialError = false}) {
    interceptor = dio.InterceptorsWrapper(
      onRequest: (options, handler) {
        final req = DmSegMobileReq.fromBuffer(
          GrpcReq.decompressProtobuf(
            Uint8List.fromList(options.data as List<int>),
          ),
        );
        final index = req.segmentIndex.toInt();
        final bytes = GrpcReq.compressProtobuf(
          DmSegMobileReply(elems: [DanmakuElem(content: 'segment-$index')])
              .writeToBuffer(),
        );
        handler.resolve(
          dio.Response<List<int>>(
            requestOptions: options,
            statusCode: 200,
            headers: dio.Headers.fromMap({
              'grpc-status': [
                initialError
                    ? '1'
                    : index == 2
                    ? '1'
                    : '0',
              ],
            }),
            data: bytes,
          ),
        );
      },
    );
    Request.dio.interceptors.add(interceptor);
  }

  setUp(installFake);
  tearDown(() => Request.dio.interceptors.remove(interceptor));

  BiliDownloadEntryInfo entry(String directory) => BiliDownloadEntryInfo(
    isCompleted: true,
    totalBytes: 0,
    downloadedBytes: 0,
    title: 'fixture',
    cover: '',
    preferedVideoQuality: 0,
    guessedTotalBytes: 0,
    totalTimeMilli: DmUtils.segLength * 3,
    danmakuCount: 0,
    avid: 1,
    bvid: 'BV1xx',
    pageData: PageInfo(cid: 123, page: 1, hasAlias: false, tid: 0),
  )..entryDirPath = directory;

  test('keeps successful segments when a middle segment errors', () async {
    final dir = await Directory.systemTemp.createTemp('dm-success');
    final result = await DownloadService().downloadDanmaku(
      entry: entry(dir.path),
      isUpdate: true,
    );
    final decoded = DmSegMobileReply.fromBuffer(
      await File('${dir.path}/${PathUtils.danmakuName}').readAsBytes(),
    );
    expect(result, isTrue);
    expect(decoded.elems.map((e) => e.content), ['segment-1', 'segment-3']);
    await dir.delete(recursive: true);
  });

  testWidgets('first segment error returns false and preserves existing file', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        builder: FlutterSmartDialog.init(),
        navigatorObservers: [FlutterSmartDialog.observer],
        home: const Scaffold(body: SizedBox()),
      ),
    );
    await tester.runAsync(() async {
      final dir = await Directory.systemTemp.createTemp('dm-first-error');
      final file = File('${dir.path}/${PathUtils.danmakuName}');
      await file.writeAsString('existing');
      Request.dio.interceptors.remove(interceptor);
      installFake(initialError: true);
      final before = await file.readAsBytes();
      final result = await DownloadService().downloadDanmaku(
        entry: entry(dir.path),
        isUpdate: true,
      );
      expect(result, isFalse);
      expect(await file.readAsBytes(), before);
      await dir.delete(recursive: true);
    });
    await tester.pump();
    await tester.pump(const Duration(seconds: 3));
    SmartDialog.dismiss(status: SmartStatus.toast);
    await tester.pumpAndSettle();
  });
}
