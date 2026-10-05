import 'dart:io';

import 'package:PiliPlus/models_new/video/video_detail/page.dart';
import 'package:PiliPlus/plugin/pl_player/models/play_status.dart';
import 'package:PiliPlus/services/audio_handler.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:audio_service/audio_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive.dart';

void main() {
  late Directory temp;
  setUpAll(() async {
    temp = await Directory.systemTemp.createTemp('audio-regression');
    Hive.init(temp.path);
    GStorage.setting = await Hive.openBox('setting');
    GStorage.video = await Hive.openBox('video');
    GStorage.localCache = await Hive.openBox('localCache');
  });
  tearDownAll(() async {
    await GStorage.setting.close();
    await GStorage.video.close();
    await GStorage.localCache.close();
    await temp.delete(recursive: true);
  });

  test(
    'suppresses duplicate second/config, keeps zero updates, clear resets',
    () async {
      final handler = VideoPlayerServiceHandler()
        ..enableBackgroundPlay = true
        ..onVideoDetailChange(Part(cid: 1, part: 'fixture'), 1, 'test');
      final states = <PlaybackState>[];
      final sub = handler.playbackState.listen(states.add);
      addTearDown(sub.cancel);
      void update(int seconds, {double speed = 1}) => handler.onUpdateState(
        PlayerStatus.playing,
        false,
        false,
        position: Duration(seconds: seconds),
        speed: speed,
      );

      update(4);
      update(4);
      update(4, speed: 2);
      update(5, speed: 2);
      update(0, speed: 2);
      update(0, speed: 2);
      await Future<void>.delayed(Duration.zero);
      expect(states.skip(1).map((s) => s.updatePosition.inSeconds), [
        4,
        4,
        5,
        0,
        0,
      ]);
      handler.clear();
      states.clear();
      handler.onVideoDetailChange(Part(cid: 2, part: 'fixture'), 2, 'test');
      update(5, speed: 2);
      await Future<void>.delayed(Duration.zero);
      expect(states.skip(1), hasLength(1));
    },
  );
}
