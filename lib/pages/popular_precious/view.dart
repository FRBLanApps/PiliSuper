import 'package:PiliSuper/common/widgets/flutter/refresh_indicator.dart';
import 'package:PiliSuper/common/widgets/loading_widget/http_error.dart';
import 'package:PiliSuper/common/widgets/video_card/video_card_h.dart';
import 'package:PiliSuper/common/widgets/view_sliver_safe_area.dart';
import 'package:PiliSuper/http/loading_state.dart';
import 'package:PiliSuper/models/common/video/source_type.dart';
import 'package:PiliSuper/models/model_hot_video_item.dart';
import 'package:PiliSuper/pages/popular_precious/controller.dart';
import 'package:PiliSuper/utils/grid.dart';
import 'package:PiliSuper/utils/page_utils.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

class PopularPreciousPage extends StatefulWidget {
  const PopularPreciousPage({super.key});

  @override
  State<PopularPreciousPage> createState() => _PopularPreciousPageState();
}

class _PopularPreciousPageState extends State<PopularPreciousPage>
    with GridMixin {
  final _controller = Get.put(PopularPreciousController());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      appBar: AppBar(title: const Text('入站必刷')),
      body: refreshIndicator(
        onRefresh: _controller.onRefresh,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            ViewSliverSafeArea(
              sliver: Obx(() => _buildBody(_controller.loadingState.value)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(LoadingState<List<HotVideoItemModel>?> value) {
    switch (value) {
      case Loading():
        return gridSkeleton;
      case Success<List<HotVideoItemModel>?>(:var response):
        return SliverGrid.builder(
          gridDelegate: gridDelegate,
          itemCount: response!.length,
          itemBuilder: (context, index) {
            final item = response[index];
            return VideoCardH(
              videoItem: item,
              onTap: () {
                PageUtils.toVideoPage(
                  bvid: item.bvid,
                  cid: item.cid!,
                  extraArguments: {
                    'sourceType': SourceType.playlist,
                    'favTitle': '入站必刷',
                    'mediaId': _controller.mediaId,
                    'desc': true,
                    'oid': item.aid,
                    'isContinuePlaying': index != 0,
                  },
                );
              },
            );
          },
        );
      case Error(:var errMsg):
        return HttpError(
          errMsg: errMsg,
          onReload: _controller.onReload,
        );
    }
  }
}
