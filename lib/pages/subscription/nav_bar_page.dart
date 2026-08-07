import 'package:PiliPlus/common/widgets/appbar/appbar.dart';
import 'package:PiliPlus/common/widgets/flutter/pop_scope.dart';
import 'package:PiliPlus/common/widgets/flutter/refresh_indicator.dart';
import 'package:PiliPlus/common/widgets/loading_widget/http_error.dart';
import 'package:PiliPlus/common/widgets/scaffold/simple_scaffold.dart';
import 'package:PiliPlus/common/widgets/view_sliver_safe_area.dart';
import 'package:PiliPlus/http/loading_state.dart';
import 'package:PiliPlus/models_new/sub/sub/list.dart';
import 'package:PiliPlus/pages/subscription/controller.dart';
import 'package:PiliPlus/pages/subscription/widgets/item.dart';
import 'package:PiliPlus/utils/grid.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// NavBar-embedded subscription page.
class SubNavBarPage extends StatefulWidget {
  const SubNavBarPage({super.key});

  @override
  State<SubNavBarPage> createState() => _SubNavBarPageState();
}

class _SubNavBarPageState extends State<SubNavBarPage> with GridMixin {
  final SubController _subController = Get.put(SubController());

  @override
  Widget build(BuildContext context) {
    return MediaQuery.removePadding(
      context: context,
      removeTop: true,
      child: Obx(() {
        final enableMultiSelect = _subController.enableMultiSelect.value;
        return popScope(
          canPop: !enableMultiSelect,
          onPopInvokedWithResult: (didPop, result) {
            if (enableMultiSelect) _subController.handleSelect();
          },
          child: SimpleScaffold(
            appBar: MultiSelectAppBarWidget(
              visible: enableMultiSelect,
              ctr: _subController,
              child: AppBar(
                automaticallyImplyLeading: false,
                actions: [
                  IconButton(
                    tooltip: '批量删除',
                    onPressed: () =>
                        _subController.enableMultiSelect.value = true,
                    icon: const Icon(Icons.checklist_outlined),
                  ),
                  const SizedBox(width: 6),
                ],
              ),
            ),
            body: refreshIndicator(
              onRefresh: _subController.onRefresh,
              child: CustomScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                slivers: [
                  ViewSliverSafeArea(
                    sliver: Obx(
                      () => _buildBody(_subController.loadingState.value),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildBody(LoadingState<List<SubItemModel>?> loadingState) {
    return switch (loadingState) {
      Loading() => gridSkeleton,
      Success(:final response) =>
        response != null && response.isNotEmpty
            ? SliverGrid.builder(
                gridDelegate: gridDelegate,
                itemBuilder: (context, index) {
                  if (index == response.length - 1) {
                    _subController.onLoadMore();
                  }
                  final item = response[index];
                  return SubItem(
                    item: item,
                    cancelSub: () => _subController.cancelSub(item),
                    enableMultiSelect: _subController.enableMultiSelect.value,
                    onSelect: () => _subController.onSelect(item),
                  );
                },
                itemCount: response.length,
              )
            : HttpError(onReload: _subController.onReload),
      Error(:final errMsg) => HttpError(
        errMsg: errMsg,
        onReload: _subController.onReload,
      ),
    };
  }
}
