import 'dart:async';

import 'package:PiliPlus/common/widgets/loading_widget/http_error.dart';
import 'package:PiliPlus/common/widgets/loading_widget/loading_widget.dart';
import 'package:PiliPlus/common/widgets/scaffold/simple_scaffold.dart';
import 'package:PiliPlus/common/widgets/view_sliver_safe_area.dart';
import 'package:PiliPlus/http/loading_state.dart';
import 'package:PiliPlus/pages/dlna/dlna_args.dart';
import 'package:PiliPlus/pages/dlna/dlna_utils.dart';
import 'package:dlna_dart/dlna.dart';
import 'package:flutter/material.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';

class DLNAPage extends StatefulWidget {
  const DLNAPage({super.key});

  @override
  State<DLNAPage> createState() => _DLNAPageState();
}

class _DLNAPageState extends State<DLNAPage> {
  final _searcher = DLNAManager();
  final Map<String, DLNADevice> _deviceList = {};
  late final _args = Get.arguments as DlnaArgs;

  Timer? _timer;
  bool _isSearching = false;
  bool _isSwitchingQa = false;
  DLNADevice? _lastDevice;
  String? _lastDeviceKey;

  @override
  void initState() {
    super.initState();
    _onSearch(isInit: true);
  }

  Future<void> _onSearch({bool isInit = false}) async {
    if (_isSearching) return;
    _isSearching = true;
    if (!isInit && mounted) {
      _lastDevice = null;
      _deviceList.clear();
      setState(() {});
    }
    final deviceManager = await _searcher.start();
    if (!mounted) {
      return;
    }
    _timer = Timer(const Duration(seconds: 20), _searcher.stop);
    await for (final deviceList in deviceManager.devices.stream) {
      if (mounted) {
        _deviceList.addAll(deviceList);
        setState(() {});
      }
    }
    if (mounted) {
      setState(() {
        _isSearching = false;
      });
    }
  }

  Future<void> _onSelectQuality(int qn) async {
    if (_isSwitchingQa || qn == _args.qn) return;
    _isSwitchingQa = true;
    SmartDialog.showLoading();
    final res = await _args.switchQuality(qn);
    if (res case Success()) {
      final device = _lastDevice;
      // 重推前记录当前播放进度，重推后恢复
      String? seekTime;
      if (device != null) {
        try {
          seekTime = parseSeekTime(
            await device.position().timeout(const Duration(seconds: 5)),
          );
        } catch (_) {}
      }
      SmartDialog.dismiss();
      if (!mounted) {
        // 页面已退出，仍完成重推以保持电视端播放
        await _rePush(device, seekTime);
        _isSwitchingQa = false;
        return;
      }
      setState(() {});
      SmartDialog.showToast('清晰度已切换为：${_args.qnDesc}');
      await _rePush(device, seekTime);
      _isSwitchingQa = false;
    } else {
      SmartDialog.dismiss();
      _isSwitchingQa = false;
      if (!mounted) return;
      res.toast();
    }
  }

  Future<void> _rePush(DLNADevice? device, String? seekTime) async {
    if (device == null) return;
    await device.setUrl(_args.url, title: _args.title ?? '');
    await device.play();
    if (seekTime != null) {
      // 部分设备就绪需要时间，seek 失败延时重试一次
      for (final wait in const [
        Duration(milliseconds: 500),
        Duration(milliseconds: 1500),
      ]) {
        await Future.delayed(wait);
        try {
          await device.seek(seekTime).timeout(const Duration(seconds: 8));
          break;
        } catch (_) {}
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _timer = null;
    _searcher.stop();
    _lastDevice = null;
    _lastDeviceKey = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.of(context);
    return SimpleScaffold(
      appBar: AppBar(
        title: const Text('投屏'),
        actions: [
          if (_args.qualities.length > 1)
            PopupMenuButton<int>(
              tooltip: '清晰度',
              initialValue: _args.qn,
              onSelected: _onSelectQuality,
              itemBuilder: (context) => _args.qualities
                  .map(
                    (item) => PopupMenuItem(
                      value: item.code,
                      child: Text(item.desc),
                    ),
                  )
                  .toList(),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  spacing: 2,
                  children: [
                    Text(_args.qnDesc),
                    const Icon(Icons.arrow_drop_down, size: 20),
                  ],
                ),
              ),
            ),
          IconButton(
            tooltip: '搜索',
            onPressed: _onSearch,
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: CustomScrollView(
        slivers: [
          if (_isSearching) linearLoading,
          ViewSliverSafeArea(sliver: _buildBody(colorScheme)),
        ],
      ),
    );
  }

  Widget _buildBody(ColorScheme colorScheme) {
    if (!_isSearching && _deviceList.isEmpty) {
      return HttpError(
        errMsg: '没有设备',
        onReload: _onSearch,
      );
    }
    if (_deviceList.isNotEmpty) {
      final keys = _deviceList.keys.toList();
      return SliverList.builder(
        itemCount: keys.length,
        itemBuilder: (context, index) {
          final key = keys[index];
          final device = _deviceList[key]!;
          final isCurr = key == _lastDeviceKey;
          return ListTile(
            title: Text(
              device.info.friendlyName,
              style: isCurr ? TextStyle(color: colorScheme.primary) : null,
            ),
            subtitle: Text(key),
            onTap: () async {
              if (isCurr) return;
              _lastDevice?.pause();
              _lastDevice = device;
              _lastDeviceKey = key;
              setState(() {});
              await device.setUrl(_args.url, title: _args.title ?? '');
              await device.play();
            },
          );
        },
      );
    }
    return const SliverToBoxAdapter();
  }
}
