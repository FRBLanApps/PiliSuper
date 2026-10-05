import 'dart:async';

import 'package:PiliPlus/models_new/download/bili_download_entry_info.dart';
import 'package:PiliPlus/pages/download/download_action_mixin.dart';
import 'package:PiliPlus/utils/extension/iterable_ext.dart';

/// Runs [toElement] over a flat entry list.
///
/// More than [kMaxUpdateCount] entries are rejected without launching, so the
/// caller can toast via the existing `false` path. At most [kUpdateConcurrency]
/// calls are in flight. Entries are chunked with an identity map; [toElement]
/// runs only after [isDismissed] is false, so a cancel — including one that is
/// already true — does not launch later work. A single `false` makes the
/// aggregate result `false`.
Future<bool> runBoundedEntryUpdate(
  Iterable<BiliDownloadEntryInfo> entries,
  Future<bool> Function(BiliDownloadEntryInfo entry) toElement,
  bool Function() isDismissed,
) async {
  if (entries.length > kMaxUpdateCount) return false;

  var isSuccess = true;
  for (final chunk in entries.mapChunked(kUpdateConcurrency, (e) => e)) {
    if (isDismissed()) break;
    final res = await Future.wait(chunk.map(toElement));
    if (res.any((e) => !e)) isSuccess = false;
    if (isDismissed()) break;
  }
  return isSuccess;
}
