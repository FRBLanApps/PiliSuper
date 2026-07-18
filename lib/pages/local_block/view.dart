import 'package:PiliPlus/common/widgets/dialog/dialog.dart';
import 'package:PiliPlus/http/danmaku_block.dart';
import 'package:PiliPlus/http/loading_state.dart';
import 'package:PiliPlus/models/common/dm_block_type.dart';
import 'package:PiliPlus/models/user/danmaku_block.dart';
import 'package:PiliPlus/models/user/danmaku_rule.dart';
import 'package:PiliPlus/pages/local_block/local_block_type.dart';
import 'package:PiliPlus/plugin/pl_player/controller.dart';
import 'package:PiliPlus/utils/ban_word_utils.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:PiliPlus/utils/storage_key.dart';
import 'package:PiliPlus/utils/storage_pref.dart';
import 'package:PiliPlus/utils/recommend_filter.dart';
import 'package:PiliPlus/utils/utils.dart';
import 'package:archive/archive.dart' show getCrc32;
import 'dart:convert' show ascii;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_smart_dialog/flutter_smart_dialog.dart';
import 'package:get/get.dart';

/// 视频过滤统一页：规则 / 弹幕 / 稿件类型 / 时长 + 作用域
class LocalBlockPage extends StatefulWidget {
  const LocalBlockPage({super.key});

  @override
  State<LocalBlockPage> createState() => _LocalBlockPageState();
}

class _LocalBlockPageState extends State<LocalBlockPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabCtr;
  final _searchCtr = TextEditingController();
  final _addCtr = TextEditingController();
  final _addFocus = FocusNode();

  LocalBlockType get _type => LocalBlockType.values[_tabCtr.index];

  List<String> _items = [];
  String _query = '';
  bool _batchMode = false;
  final Set<int> _selected = {};

  // 弹幕
  final List<RxList<SimpleRule>> _dmRules = List.generate(
    DmBlockType.values.length,
    (_) => <SimpleRule>[].obs,
  );
  int _dmSubTab = 0;
  bool _dmLoaded = false;
  bool _dmLoading = false;

  // 稿件类型
  late Set<String> _blockedTypes;

  // 时长
  late int _minDuration;

  // 作用域
  late bool _scopeRelated;
  late bool _scopeHot;
  late bool _scopeRank;
  late bool _scopeSearch;

  List<(int, String)> get _filteredEntries {
    if (_query.isEmpty) {
      return [for (var i = 0; i < _items.length; i++) (i, _items[i])];
    }
    final q = _query.toLowerCase();
    return [
      for (var i = 0; i < _items.length; i++)
        if (_items[i].toLowerCase().contains(q)) (i, _items[i]),
    ];
  }

  @override
  void initState() {
    super.initState();
    final initial = Get.arguments;
    var initIndex = 0;
    // 兼容 /danmakuBlock 旧入口与 {'tab': 'danmaku'}
    if (initial is Map && initial['tab'] is String) {
      final name = initial['tab'] as String;
      final i = LocalBlockType.values.indexWhere((e) => e.name == name);
      if (i >= 0) initIndex = i;
    } else if (Get.currentRoute.contains('danmakuBlock')) {
      initIndex = LocalBlockType.danmaku.index;
    }
    _tabCtr = TabController(
      length: LocalBlockType.values.length,
      vsync: this,
      initialIndex: initIndex,
    )..addListener(_onTabChanged);

    _blockedTypes = Pref.blockedRcmdTypes;
    _minDuration = Pref.minDurationForRcmd;
    _scopeRelated = Pref.applyFilterToRelatedVideos;
    _scopeHot = Pref.applyFilterToHotVideos;
    _scopeRank = Pref.applyFilterToRankVideos;
    _scopeSearch = Pref.applyFilterToSearch;

    _reload();
    if (_type.isDanmaku) {
      _loadDanmaku();
    }
  }

  void _onTabChanged() {
    if (_tabCtr.indexIsChanging) return;
    setState(() {
      _batchMode = false;
      _selected.clear();
      _searchCtr.clear();
      _query = '';
      _addCtr.clear();
      _reload();
    });
    if (_type.isDanmaku && !_dmLoaded) {
      _loadDanmaku();
    }
  }

  void _reload() {
    if (_type.isKeywordList || _type.isUp) {
      _items = _type.loadRules();
    }
  }

  Future<void> _loadDanmaku() async {
    if (_dmLoading) return;
    _dmLoading = true;
    SmartDialog.showLoading(msg: '正在同步弹幕屏蔽规则…');
    final result = await DanmakuFilterHttp.danmakuFilter();
    SmartDialog.dismiss();
    _dmLoading = false;
    if (!mounted) return;
    if (result case Success(:final response)) {
      for (final list in _dmRules) {
        list.clear();
      }
      _dmRules[0].addAll(response.rule);
      _dmRules[1].addAll(response.rule1);
      _dmRules[2].addAll(response.rule2);
      _dmLoaded = true;
      setState(() {});
      if (response.toast case final toast?) {
        SmartDialog.showToast(toast);
      }
    } else {
      result.toast();
    }
  }

  void _applyDanmakuToPlayer() {
    final filter = RuleFilter.fromRuleTypeEntries(
      List<List<SimpleRule>>.generate(
        _dmRules.length,
        (i) => _dmRules[i].toList(),
      ),
    );
    GStorage.localCache.put(LocalCacheKey.danmakuFilterRules, filter);
    if (PlPlayerController.instanceExists()) {
      PlPlayerController.getInstance().filters = filter;
    }
  }

  @override
  void dispose() {
    if (_dmLoaded) {
      _applyDanmakuToPlayer();
    }
    _tabCtr
      ..removeListener(_onTabChanged)
      ..dispose();
    _searchCtr.dispose();
    _addCtr.dispose();
    _addFocus.dispose();
    super.dispose();
  }

  Future<void> _persist(List<String> next) async {
    _type.saveRules(next);
    setState(() {
      _items = next;
      _batchMode = false;
      _selected.clear();
    });
  }

  Future<void> _confirmAdd() async {
    final text = _addCtr.text.trim();
    if (text.isEmpty) {
      SmartDialog.showToast('请输入内容');
      return;
    }
    if (_type.isUp) {
      final uid = int.tryParse(text);
      if (uid == null || uid <= 0) {
        SmartDialog.showToast('UID 无效');
        return;
      }
      final display = 'UID:$uid ($uid)';
      if (Pref.recommendBlockedMids.containsKey(uid)) {
        SmartDialog.showToast('该 UP 已在列表中');
        return;
      }
      final ok = await showConfirmDialog(
        context: context,
        title: const Text('确认添加'),
        content: Text('将本地屏蔽 UP：$uid'),
      );
      if (!ok || !mounted) return;
      await _persist([..._items, display]);
      _addCtr.clear();
      SmartDialog.showToast('已添加');
      return;
    }
    if (_type.isDanmaku) {
      await _dmAdd(text);
      return;
    }
    if (!_type.isKeywordList) return;
    if (_items.contains(text)) {
      SmartDialog.showToast('该规则已存在');
      return;
    }
    final ok = await showConfirmDialog(
      context: context,
      title: const Text('确认添加'),
      content: Text(text),
    );
    if (!ok || !mounted) return;
    await _persist([..._items, text]);
    _addCtr.clear();
    SmartDialog.showToast('已添加');
  }

  Future<void> _dmAdd(String text) async {
    var filter = text;
    // 正则 Tab：JS /pat/flags → 云端裸 pattern
    if (_dmSubTab == 1) {
      filter = BanWordUtils.toCloudDanmakuRegex(text);
      if (filter.isEmpty) {
        SmartDialog.showToast('正则无效');
        return;
      }
    }
    final ok = await showConfirmDialog(
      context: context,
      title: const Text('确认添加弹幕规则'),
      content: Text(text),
    );
    if (!ok || !mounted) return;
    SmartDialog.showLoading(msg: '正在添加…');
    var toSend = filter;
    if (_dmSubTab == 2) {
      final uid = int.tryParse(filter);
      if (uid == null || uid <= 0) {
        SmartDialog.showToast('UID 无效');
        return;
      }
      toSend = getCrc32(ascii.encode(filter), 0).toRadixString(16);
    }
    final res = await DanmakuFilterHttp.danmakuFilterAdd(
      filter: toSend,
      type: _dmSubTab,
    );
    SmartDialog.dismiss();
    if (res case Success(:final response)) {
      _dmRules[_dmSubTab].add(response);
      _applyDanmakuToPlayer();
      SmartDialog.showToast('添加成功');
      _addCtr.clear();
      setState(() {});
    } else {
      res.toast();
    }
  }

  Future<void> _confirmEdit(int rawIndex, String oldValue) async {
    final ctr = TextEditingController(text: oldValue);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('修改规则'),
        content: TextField(
          controller: ctr,
          autofocus: true,
          decoration: InputDecoration(hintText: _type.addHint),
          maxLines: 3,
        ),
        actions: [
          TextButton(onPressed: Get.back, child: const Text('取消')),
          TextButton(
            onPressed: () => Get.back(result: ctr.text.trim()),
            child: const Text('确定'),
          ),
        ],
      ),
    );
    ctr.dispose();
    if (result == null || !mounted) return;
    if (result.isEmpty) {
      SmartDialog.showToast('内容不能为空');
      return;
    }
    if (result == oldValue) return;
    if (_items.contains(result)) {
      SmartDialog.showToast('该规则已存在');
      return;
    }
    final ok = await showConfirmDialog(
      context: context,
      title: const Text('确认修改'),
      content: Text('$oldValue\n→\n$result'),
    );
    if (!ok || !mounted) return;
    final next = List<String>.from(_items)..[rawIndex] = result;
    await _persist(next);
    SmartDialog.showToast('已修改');
  }

  Future<void> _confirmDeleteOne(int rawIndex, String value) async {
    final ok = await showConfirmDialog(
      context: context,
      title: const Text('确认删除'),
      content: Text(value),
    );
    if (!ok || !mounted) return;
    final next = List<String>.from(_items)..removeAt(rawIndex);
    await _persist(next);
    SmartDialog.showToast('已删除');
  }

  Future<void> _confirmBatchDelete() async {
    if (_selected.isEmpty) {
      SmartDialog.showToast('请先选择要删除的项');
      return;
    }
    final toDelete =
        _selected.where((i) => i >= 0 && i < _items.length).toList()
          ..sort((a, b) => b.compareTo(a));
    if (toDelete.isEmpty) return;
    final preview = toDelete.map((i) => _items[i]).take(5).join('\n');
    final ok = await showConfirmDialog(
      context: context,
      title: Text('确认删除 ${toDelete.length} 项'),
      content: Text(preview + (toDelete.length > 5 ? '\n…' : '')),
    );
    if (!ok || !mounted) return;
    final next = List<String>.from(_items);
    for (final i in toDelete) {
      next.removeAt(i);
    }
    await _persist(next);
    SmartDialog.showToast('已删除');
  }

  void _toggleBatchMode() {
    setState(() {
      _batchMode = !_batchMode;
      _selected.clear();
    });
  }

  void _showScopeMenu() {
    showModalBottomSheet(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModal) {
            Widget tile(String title, String? sub, bool value, ValueChanged<bool> onChanged) {
              return SwitchListTile(
                title: Text(title),
                subtitle: sub != null ? Text(sub) : null,
                value: value,
                onChanged: (v) {
                  onChanged(v);
                  setModal(() {});
                  setState(() {});
                },
              );
            }

            return SafeArea(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const ListTile(title: Text('过滤器作用域')),
                  tile(
                    '应用到相关视频',
                    '详情页推荐相关',
                    _scopeRelated,
                    (v) {
                      _scopeRelated = v;
                      RecommendFilter.applyFilterToRelatedVideos = v;
                      GStorage.setting.put(
                        SettingBoxKey.applyFilterToRelatedVideos,
                        v,
                      );
                    },
                  ),
                  tile(
                    '应用到热门视频',
                    null,
                    _scopeHot,
                    (v) {
                      _scopeHot = v;
                      RecommendFilter.applyFilterToHotVideos = v;
                      GStorage.setting.put(
                        SettingBoxKey.applyFilterToHotVideos,
                        v,
                      );
                    },
                  ),
                  tile(
                    '应用到分区/排行',
                    null,
                    _scopeRank,
                    (v) {
                      _scopeRank = v;
                      RecommendFilter.applyFilterToRankVideos = v;
                      GStorage.setting.put(
                        SettingBoxKey.applyFilterToRankVideos,
                        v,
                      );
                    },
                  ),
                  tile(
                    '应用到搜索结果',
                    '仅过滤标题关键词与本地屏蔽 UP',
                    _scopeSearch,
                    (v) {
                      _scopeSearch = v;
                      RecommendFilter.applyFilterToSearch = v;
                      GStorage.setting.put(
                        SettingBoxKey.applyFilterToSearch,
                        v,
                      );
                    },
                  ),
                  const SizedBox(height: 8),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isBatch = _batchMode;

    return Scaffold(
      appBar: AppBar(
        title: const Text('视频过滤'),
        actions: [
          IconButton(
            tooltip: '作用域',
            icon: const Icon(Icons.tune),
            onPressed: _showScopeMenu,
          ),
        ],
        bottom: TabBar(
          controller: _tabCtr,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          tabs: [
            for (final t in LocalBlockType.values) Tab(text: t.label),
          ],
        ),
      ),
      body: switch (_type) {
        LocalBlockType.duration => _buildDurationTab(theme),
        LocalBlockType.rcmdType => _buildRcmdTypeTab(theme),
        LocalBlockType.danmaku => _buildDanmakuTab(theme),
        _ => _buildListTab(theme, isBatch),
      },
    );
  }

  Widget _buildDurationTab(ThemeData theme) {
    const values = [0, 30, 60, 90, 120, 180, 300];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '过滤掉时长小于设定值的视频（0 表示不过滤）',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.outline,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final v in values)
              ChoiceChip(
                label: Text(v == 0 ? '不过滤' : '${v}s'),
                selected: _minDuration == v,
                onSelected: (_) async {
                  final ok = await showConfirmDialog(
                    context: context,
                    title: const Text('确认修改时长过滤'),
                    content: Text(v == 0 ? '不过滤' : '最小时长 ${v}s'),
                  );
                  if (!ok || !mounted) return;
                  setState(() => _minDuration = v);
                  RecommendFilter.minDurationForRcmd = v;
                  GStorage.setting.put(SettingBoxKey.minDurationForRcmd, v);
                  SmartDialog.showToast('已保存');
                },
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildRcmdTypeTab(ThemeData theme) {
    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 8),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Text(
            '勾选后，首页推荐将隐藏对应类型稿件（广告始终过滤）',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.outline,
            ),
          ),
        ),
        for (final t in RcmdBlockType.values)
          CheckboxListTile(
            title: Text(t.label),
            subtitle: Text(t.goto),
            value: _blockedTypes.contains(t.goto),
            onChanged: (v) async {
              final next = Set<String>.from(_blockedTypes);
              if (v == true) {
                next.add(t.goto);
              } else {
                next.remove(t.goto);
              }
              final ok = await showConfirmDialog(
                context: context,
                title: const Text('确认修改稿件类型屏蔽'),
                content: Text(
                  v == true ? '屏蔽：${t.label}' : '取消屏蔽：${t.label}',
                ),
              );
              if (!ok || !mounted) return;
              setState(() => _blockedTypes = next);
              Pref.blockedRcmdTypes = next;
              RecommendFilter.blockedRcmdTypes = next;
              SmartDialog.showToast('已保存');
            },
          ),
      ],
    );
  }

  Widget _buildDanmakuTab(ThemeData theme) {
    return Column(
      children: [
        SegmentedButton<int>(
          segments: [
            for (var i = 0; i < DmBlockType.values.length; i++)
              ButtonSegment(value: i, label: Text(DmBlockType.values[i].label)),
          ],
          selected: {_dmSubTab},
          onSelectionChanged: (s) => setState(() => _dmSubTab = s.first),
        ),
        Expanded(
          child: Obx(() {
            final list = _dmRules[_dmSubTab];
            if (list.isEmpty) {
              return Center(
                child: Text(
                  _dmLoaded ? '暂无规则' : '加载中…',
                  style: TextStyle(color: theme.colorScheme.outline),
                ),
              );
            }
            return ListView.builder(
              itemCount: list.length,
              itemBuilder: (context, index) {
                final rule = list[index];
                final display = _dmSubTab == 1
                    ? BanWordUtils.fromCloudDanmakuRegex(rule.filter)
                    : rule.filter;
                return ListTile(
                  title: Text(display),
                  trailing: IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () async {
                      final ok = await showConfirmDialog(
                        context: context,
                        title: const Text('确认删除弹幕规则'),
                        content: Text(display),
                      );
                      if (!ok || !mounted) return;
                      SmartDialog.showLoading(msg: '删除中…');
                      final res = await DanmakuFilterHttp.danmakuFilterDel(
                        ids: rule.id,
                      );
                      SmartDialog.dismiss();
                      if (res.isSuccess) {
                        list.removeAt(index);
                        _applyDanmakuToPlayer();
                        SmartDialog.showToast('已删除');
                      } else {
                        res.toast();
                      }
                    },
                  ),
                );
              },
            );
          }),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _addCtr,
                    decoration: InputDecoration(
                      isDense: true,
                      hintText: switch (_dmSubTab) {
                        0 => '关键词',
                        1 => '正则：/pattern/ 或裸 pattern',
                        _ => '用户 UID',
                      },
                      border: const OutlineInputBorder(),
                    ),
                    keyboardType: _dmSubTab == 2
                        ? TextInputType.number
                        : TextInputType.text,
                    onSubmitted: (_) => _confirmAdd(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _confirmAdd,
                  child: const Text('添加'),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildListTab(ThemeData theme, bool isBatch) {
    final filtered = _filteredEntries;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtr,
                  decoration: const InputDecoration(
                    isDense: true,
                    hintText: '搜索',
                    prefixIcon: Icon(Icons.search, size: 20),
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 8,
                    ),
                  ),
                  onChanged: (v) => setState(() => _query = v.trim()),
                ),
              ),
              IconButton(
                tooltip: isBatch ? '取消批量' : '批量删除',
                onPressed: _toggleBatchMode,
                style: IconButton.styleFrom(
                  backgroundColor: isBatch
                      ? theme.colorScheme.errorContainer
                      : null,
                  foregroundColor: isBatch
                      ? theme.colorScheme.onErrorContainer
                      : theme.colorScheme.onSurfaceVariant,
                ),
                icon: Icon(
                  isBatch ? Icons.close : Icons.auto_delete_outlined,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(
                  child: Text(
                    _items.isEmpty ? '暂无规则' : '无匹配结果',
                    style: TextStyle(color: theme.colorScheme.outline),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final (rawIndex, value) = filtered[index];
                    final selected = _selected.contains(rawIndex);
                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 4,
                      ),
                      child: ListTile(
                        dense: true,
                        leading: isBatch
                            ? Checkbox(
                                value: selected,
                                onChanged: (v) {
                                  setState(() {
                                    if (v == true) {
                                      _selected.add(rawIndex);
                                    } else {
                                      _selected.remove(rawIndex);
                                    }
                                  });
                                },
                              )
                            : null,
                        title: Text(value, maxLines: 3),
                        onTap: () {
                          if (isBatch) {
                            setState(() {
                              if (selected) {
                                _selected.remove(rawIndex);
                              } else {
                                _selected.add(rawIndex);
                              }
                            });
                            return;
                          }
                          if (_type.isUp) {
                            SmartDialog.showToast(
                              'UP 项不支持直接改名，可删除后重新添加',
                            );
                            return;
                          }
                          _confirmEdit(rawIndex, value);
                        },
                        onLongPress: () => Utils.copyText(value),
                        trailing: isBatch
                            ? null
                            : Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  IconButton(
                                    tooltip: '复制',
                                    icon: const Icon(Icons.copy, size: 20),
                                    onPressed: () => Utils.copyText(value),
                                  ),
                                  IconButton(
                                    tooltip: '删除',
                                    icon: const Icon(Icons.close, size: 20),
                                    onPressed: () =>
                                        _confirmDeleteOne(rawIndex, value),
                                  ),
                                ],
                              ),
                      ),
                    );
                  },
                ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            child: isBatch
                ? SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: theme.colorScheme.error,
                        foregroundColor: theme.colorScheme.onError,
                      ),
                      onPressed: _confirmBatchDelete,
                      child: Text('删除所选 (${_selected.length})'),
                    ),
                  )
                : Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _addCtr,
                          focusNode: _addFocus,
                          keyboardType: _type.isUp
                              ? TextInputType.number
                              : TextInputType.text,
                          inputFormatters: _type.isUp
                              ? [FilteringTextInputFormatter.digitsOnly]
                              : null,
                          decoration: InputDecoration(
                            isDense: true,
                            hintText: _type.addHint,
                            border: const OutlineInputBorder(),
                          ),
                          onSubmitted: (_) => _confirmAdd(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(
                        onPressed: _confirmAdd,
                        child: const Text('添加'),
                      ),
                    ],
                  ),
          ),
        ),
      ],
    );
  }
}
