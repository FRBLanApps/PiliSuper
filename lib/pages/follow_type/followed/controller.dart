import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/http/user.dart';
import 'package:PiliSuper/models_new/follow/data.dart';
import 'package:PiliSuper/pages/follow_type/controller.dart';

class FollowedController extends FollowTypeController {
  @override
  Future<LoadingState<FollowData>> customGetData() =>
      UserHttp.followedUp(mid: mid, pn: page);
}
