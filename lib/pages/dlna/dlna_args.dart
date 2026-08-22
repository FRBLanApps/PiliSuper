import 'package:PiliPlus/http/loading_state.dart';
import 'package:PiliPlus/http/video.dart';
import 'package:PiliPlus/models/common/video/video_quality.dart';
import 'package:PiliPlus/models/video/play/url.dart';
import 'package:PiliPlus/utils/video_utils.dart';
import 'package:collection/collection.dart' show IterableExtension;

/// 投屏可选清晰度
class CastQuality {
  const CastQuality(this.code, this.desc);

  final int code;
  final String desc;
}

typedef _CastSource = ({String url, int qn, List<CastQuality> qualities});

/// 投屏页参数，同时负责按清晰度获取投屏地址
class DlnaArgs {
  DlnaArgs({
    required this.cid,
    required this.objectId,
    required this.playurlType,
    required this.url,
    required this.qn,
    required this.qualities,
    this.title,
  });

  final int cid;

  /// aid or epId
  final int objectId;

  /// ugc 1, pgc 2
  final int playurlType;

  final String? title;

  /// 当前投屏地址
  String url;

  /// 当前清晰度
  int qn;

  /// 可选清晰度，为空表示该视频不支持切换
  List<CastQuality> qualities;

  String get qnDesc =>
      qualities.firstWhereOrNull((e) => e.code == qn)?.desc ??
      VideoQuality.tryFromCode(qn)?.desc ??
      qn.toString();

  static Future<LoadingState<DlnaArgs>> create({
    required int cid,
    required int objectId,
    required int playurlType,
    int? qn,
    String? title,
  }) async {
    final res = await _request(
      cid: cid,
      objectId: objectId,
      playurlType: playurlType,
      qn: qn,
    );
    return switch (res) {
      Success(:final response) => Success(
        DlnaArgs(
          cid: cid,
          objectId: objectId,
          playurlType: playurlType,
          title: title,
          url: response.url,
          qn: response.qn,
          qualities: response.qualities,
        ),
      ),
      _ => res as LoadingState<DlnaArgs>,
    };
  }

  /// 切换清晰度，成功后 [url] / [qn] 已更新
  Future<LoadingState<DlnaArgs>> switchQuality(int newQn) async {
    final res = await _request(
      cid: cid,
      objectId: objectId,
      playurlType: playurlType,
      qn: newQn,
    );
    if (res case Success(:final response)) {
      url = response.url;
      qn = response.qn;
      if (response.qualities.isNotEmpty) {
        qualities = response.qualities;
      }
      return Success(this);
    }
    return res as LoadingState<DlnaArgs>;
  }

  static Future<LoadingState<_CastSource>> _request({
    required int cid,
    required int objectId,
    required int playurlType,
    int? qn,
  }) async {
    final res = await VideoHttp.tvPlayUrl(
      cid: cid,
      objectId: objectId,
      playurlType: playurlType,
      qn: qn,
    );
    if (res case Success(:final response)) {
      final first = response.durl?.firstOrNull;
      if (first == null || first.playUrls.isEmpty) {
        return const Error('不支持投屏');
      }
      return Success((
        url: VideoUtils.getCdnUrl(first.playUrls),
        qn: response.quality ?? qn ?? 80,
        qualities: parseQualities(response),
      ));
    }
    return res as LoadingState<_CastSource>;
  }

  /// 从 playurl 响应解析可选清晰度
  static List<CastQuality> parseQualities(PlayUrlModel data) {
    final codes = data.acceptQuality;
    if (codes == null || codes.isEmpty) return const [];
    final descList = data.acceptDesc;
    return List.generate(codes.length, (index) {
      final code = codes[index];
      final desc = descList != null && index < descList.length
          ? descList[index]
          : null;
      return CastQuality(
        code,
        desc is String && desc.isNotEmpty
            ? desc
            : VideoQuality.tryFromCode(code)?.desc ?? code.toString(),
      );
    });
  }
}
