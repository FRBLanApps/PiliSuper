import 'package:PiliSuper/http/dynamics.dart';
import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/models_new/dynamic/dyn_topic_top/topic_item.dart';
import 'package:PiliSuper/pages/common/common_list_controller.dart';

class DynTopicRcmdController
    extends CommonListController<List<TopicItem>?, TopicItem> {
  @override
  void onInit() {
    super.onInit();
    queryData();
  }

  @override
  Future<LoadingState<List<TopicItem>?>> customGetData() =>
      DynamicsHttp.dynTopicRcmd();
}
