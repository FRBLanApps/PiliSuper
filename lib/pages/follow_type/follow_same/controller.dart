import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/http/user.dart';
import 'package:PiliSuper/models_new/follow/data.dart';
import 'package:PiliSuper/pages/follow_type/controller.dart';

class FollowSameController extends FollowTypeController {
  @override
  Future<LoadingState<FollowData>> customGetData() =>
      UserHttp.sameFollowing(mid: mid, pn: page);
}
