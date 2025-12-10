import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/http/video.dart';
import 'package:PiliSuper/models/model_hot_video_item.dart';
import 'package:PiliSuper/pages/common/common_list_controller.dart';
import 'package:PiliSuper/utils/storage_pref.dart';
import 'package:get/get.dart';

class HotController
    extends CommonListController<List<HotVideoItemModel>, HotVideoItemModel> {
  final RxBool showHotRcmd = Pref.showHotRcmd.obs;

  @override
  void onInit() {
    super.onInit();
    queryData();
  }

  @override
  Future<LoadingState<List<HotVideoItemModel>>> customGetData() =>
      VideoHttp.hotVideoList(
        pn: page,
        ps: 20,
      );
}
