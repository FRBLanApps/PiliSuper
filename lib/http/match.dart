import 'package:PiliSuper/http/api.dart';
import 'package:PiliSuper/http/init.dart';
import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/models_new/match/match_info/contest.dart';
import 'package:PiliSuper/models_new/match/match_info/data.dart';

class MatchHttp {
  static Future<LoadingState<MatchContest?>> matchInfo(dynamic cid) async {
    var res = await Request().get(
      Api.matchInfo,
      queryParameters: {
        'cid': cid,
        'platform': 2,
      },
    );
    if (res.data['code'] == 0) {
      return Success(MatchInfoData.fromJson(res.data['data']).contest);
    } else {
      return Error(res.data['message']);
    }
  }
}
