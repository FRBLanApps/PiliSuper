import 'package:PiliSuper/http/fan.dart';
import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/http/video.dart';
import 'package:PiliSuper/models_new/follow/data.dart';
import 'package:PiliSuper/pages/follow_type/controller.dart';
import 'package:PiliSuper/utils/accounts.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';

class FansController extends FollowTypeController {
  FansController(this.showName);
  final bool showName;
  late final bool isOwner;

  @override
  void init() {
    final Map? args = Get.arguments;
    final ownerMid = Accounts.main.mid;
    final int? mid = args?['mid'];
    this.mid = mid ?? ownerMid;
    isOwner = ownerMid == this.mid;
    if (showName && !isOwner) {
      final String? name = args?['name'];
      this.name = RxnString(name);
      if (name == null) {
        queryUserName();
      }
    }
    queryData();
  }

  @override
  Future<LoadingState<FollowData>> customGetData() => FanHttp.fans(
    vmid: mid,
    pn: page,
    orderType: 'attention',
  );

  Future<void> onRemoveFan(int index, int mid) async {
    final res = await VideoHttp.relationMod(
      mid: mid,
      act: 7,
      reSrc: 11,
    );
    if (res['status']) {
      loadingState
        ..value.data!.removeAt(index)
        ..refresh();
      SmartDialog.showToast('移除成功');
    } else {
      SmartDialog.showToast(res['msg']);
    }
  }
}
