import 'package:PiliSuper/grpc/bilibili/app/viewunite/v1.pb.dart'
    show ViewReq, ViewReply;
import 'package:PiliSuper/grpc/grpc_req.dart';
import 'package:PiliSuper/grpc/url.dart';
import 'package:PiliSuper/http/loading_state.dart';

class ViewGrpc {
  static Future<LoadingState<ViewReply>> view({
    required String bvid,
  }) {
    return GrpcReq.request(
      GrpcUrl.view,
      ViewReq(
        bvid: bvid,
      ),
      ViewReply.fromBuffer,
    );
  }
}
