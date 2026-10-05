import 'dart:async';

import 'package:PiliPlus/models_new/download/bili_download_entry_info.dart';
import 'package:PiliPlus/pages/download/bounded_update.dart';
import 'package:PiliPlus/pages/download/download_action_mixin.dart';
import 'package:flutter_test/flutter_test.dart';

BiliDownloadEntryInfo _entry(int id) => BiliDownloadEntryInfo(
  isCompleted: true,
  totalBytes: 0,
  downloadedBytes: 0,
  title: 't$id',
  cover: '',
  preferedVideoQuality: 16,
  guessedTotalBytes: 0,
  totalTimeMilli: 0,
  danmakuCount: 0,
  avid: 1,
  bvid: 'BV1',
  pageData: PageInfo(cid: id, page: 1, hasAlias: false, tid: 0),
);

void main() {
  test(
    'stays at concurrency 10 and does not launch the next batch after cancel',
    () async {
      final entries = List.generate(25, _entry);
      final gates = List.generate(25, (_) => Completer<bool>());
      var started = 0;
      var inFlight = 0;
      var maxInFlight = 0;
      var dismiss = false;

      final pending = runBoundedEntryUpdate(entries, (entry) {
        started++;
        inFlight++;
        if (inFlight > maxInFlight) maxInFlight = inFlight;
        final index = entry.cid;
        return gates[index].future.whenComplete(() => inFlight--);
      }, () => dismiss);

      await pumpEventQueue();
      expect(started, kUpdateConcurrency);
      expect(maxInFlight, kUpdateConcurrency);

      dismiss = true;
      for (var i = 0; i < kUpdateConcurrency; i++) {
        gates[i].complete(true);
      }
      await pending;

      expect(started, kUpdateConcurrency);
      expect(maxInFlight, kUpdateConcurrency);
    },
  );

  test('an already cancelled run launches nothing', () async {
    var started = 0;
    final isSuccess = await runBoundedEntryUpdate(
      List.generate(12, _entry),
      (entry) async {
        started++;
        return true;
      },
      () => true,
    );
    expect(started, 0);
    expect(isSuccess, isTrue);
  });

  test('a selection over 1000 entries launches nothing', () async {
    var started = 0;
    final isSuccess = await runBoundedEntryUpdate(
      List.generate(kMaxUpdateCount + 1, _entry),
      (entry) async {
        started++;
        return true;
      },
      () => false,
    );
    expect(started, 0);
    expect(isSuccess, isFalse);
  });

  test('mixed batch results aggregate to failure', () async {
    final entries = List.generate(12, _entry);
    final isSuccess = await runBoundedEntryUpdate(entries, (entry) async {
      return entry.cid.isEven;
    }, () => false);
    expect(isSuccess, isFalse);
  });
}
