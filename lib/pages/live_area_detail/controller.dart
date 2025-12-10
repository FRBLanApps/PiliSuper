import 'dart:math';

import 'package:PiliSuper/http/live.dart';
import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/models_new/live/live_area_list/area_item.dart';
import 'package:PiliSuper/pages/common/common_list_controller.dart';

class LiveAreaDetailController
    extends CommonListController<List<AreaItem>?, AreaItem> {
  LiveAreaDetailController(this.areaId, this.parentAreaId);
  final dynamic areaId;
  final dynamic parentAreaId;

  late int initialIndex = 0;

  @override
  void onInit() {
    super.onInit();
    queryData();
  }

  @override
  List<AreaItem>? getDataList(List<AreaItem>? response) {
    if (response != null && response.isNotEmpty) {
      initialIndex = max(0, response.indexWhere((e) => e.id == areaId));
    }
    return response;
  }

  @override
  Future<LoadingState<List<AreaItem>?>> customGetData() =>
      LiveHttp.liveRoomAreaList(parentid: parentAreaId);
}
