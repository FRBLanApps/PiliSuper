import 'dart:async';

import 'package:PiliPlus/http/loading_state.dart';
import 'package:PiliPlus/http/video.dart';
import 'package:PiliPlus/models/model_video.dart';
import 'package:PiliPlus/pages/common/common_list_controller.dart';
import 'package:PiliPlus/utils/rcmd_meta_prefetch.dart';
import 'package:PiliPlus/utils/storage_pref.dart';

class RcmdController extends CommonListController {
  late bool enableSaveLastData = Pref.enableSaveLastData;
  final bool appRcmd = Pref.appRcmd;

  int? lastRefreshAt;
  late bool savedRcmdTip = Pref.savedRcmdTip;

  int _prefetchGen = 0;

  @override
  bool get isEnd => false;

  @override
  void onInit() {
    super.onInit();
    page = 0;
    queryData();
  }

  @override
  Future<LoadingState> customGetData() {
    return appRcmd
        ? VideoHttp.rcmdVideoListApp(freshIdx: page)
        : VideoHttp.rcmdVideoList(freshIdx: page, ps: 20);
  }

  @override
  bool handleError(String? errMsg) {
    return enableSaveLastData;
  }

  @override
  void handleListResponse(List dataList) {
    if (enableSaveLastData && page == 0) {
      if (loadingState.value case Success(:final response)) {
        if (response != null && response.isNotEmpty) {
          if (savedRcmdTip) {
            lastRefreshAt = dataList.length;
          }
          if (response.length > 200) {
            dataList.addAll(response.take(50));
          } else {
            dataList.addAll(response);
          }
        }
      }
    }
    // 异步预取 TAG/话题，命中规则后从列表移除
    _scheduleMetaPrefetch(List.from(dataList));
  }

  void _scheduleMetaPrefetch(List batch) {
    final gen = ++_prefetchGen;
    unawaited(() async {
      final blocked = await RcmdMetaPrefetch.prefetchAndCollectBlocked(
        batch,
        isCancelled: () => gen != _prefetchGen || isClosed,
      );
      if (blocked.isEmpty || gen != _prefetchGen || isClosed) return;
      if (loadingState.value case Success(:final response)) {
        if (response == null || response.isEmpty) return;
        final next = response.where((e) {
          if (e is BaseVideoItemModel) {
            return e.bvid == null || !blocked.contains(e.bvid);
          }
          return true;
        }).toList();
        if (next.length != response.length) {
          loadingState.value = Success(next);
        }
      }
    }());
  }

  @override
  Future<void> onRefresh() {
    page = 0;
    isEnd = false;
    _prefetchGen++;
    return queryData();
  }
}
