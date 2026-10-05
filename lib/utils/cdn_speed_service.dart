import 'package:PiliPlus/http/browser_ua.dart';
import 'package:PiliPlus/http/constants.dart';
import 'package:PiliPlus/http/video.dart';
import 'package:PiliPlus/models/common/video/cdn_type.dart';
import 'package:PiliPlus/models/common/video/video_quality.dart';
import 'package:PiliPlus/models/common/video/video_type.dart';
import 'package:PiliPlus/models/video/play/url.dart';
import 'package:PiliPlus/utils/storage.dart';
import 'package:PiliPlus/utils/storage_key.dart';
import 'package:PiliPlus/utils/video_utils.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kDebugMode, debugPrint;

typedef CdnSpeedProgress = void Function(CDNService service, String result);

/// CDN 测速与自动切换
abstract final class CdnSpeedService {
  static bool _testing = false;
  static bool get isTesting => _testing;

  static DateTime? _lastAutoSwitchAt;
  static const _autoSwitchCooldown = Duration(minutes: 2);

  /// 成功切换并继续播放后的稳定期：运营商 QoS / 重载缓冲期间不触发
  static DateTime? _lastSuccessfulSwitchAt;
  static const postSwitchSettle = Duration(minutes: 1);

  /// 全局：滑动时间窗内最多自动测速次数（防弱网连刷烧流量）
  static const maxAttemptsInWindow = 3;
  static const attemptWindow = Duration(minutes: 15);
  static final List<DateTime> _attemptTimestamps = [];

  /// 单视频（含分 P）自动测速上限：弱网下再测也帮不上忙
  static const maxAttemptsPerVideo = 2;

  /// 自动切换时用更轻量的测速，降低流量与耗时
  static const _autoMaxSize = 2 * 1024 * 1024;
  static const _autoTimeout = Duration(seconds: 5);
  static const _manualMaxSize = 8 * 1024 * 1024;
  static const _manualTimeout = Duration(seconds: 15);

  static void _pruneAttempts(DateTime now) {
    _attemptTimestamps.removeWhere(
      (t) => now.difference(t) > attemptWindow,
    );
  }

  /// 成功切换后 1 分钟内：不计卡顿、不自动测速（等线路稳定）
  static bool inPostSwitchSettle({DateTime? now}) {
    now ??= DateTime.now();
    return _lastSuccessfulSwitchAt != null &&
        now.difference(_lastSuccessfulSwitchAt!) < postSwitchSettle;
  }

  static void markSuccessfulSwitch() {
    _lastSuccessfulSwitchAt = DateTime.now();
  }

  /// 是否允许再发起一轮自动测速（不含单视频计数，由调用方维护）
  static bool canAutoAttempt({DateTime? now}) {
    if (_testing) return false;
    now ??= DateTime.now();
    if (inPostSwitchSettle(now: now)) {
      return false;
    }
    if (_lastAutoSwitchAt != null &&
        now.difference(_lastAutoSwitchAt!) < _autoSwitchCooldown) {
      return false;
    }
    _pruneAttempts(now);
    return _attemptTimestamps.length < maxAttemptsInWindow;
  }

  /// 尝试占用一次全局额度；成功返回 true 并已记账
  static bool tryReserveAttempt() {
    final now = DateTime.now();
    if (!canAutoAttempt(now: now)) return false;
    _attemptTimestamps.add(now);
    return true;
  }

  static Future<BaseItem> getSampleUrl() async {
    final result = await VideoHttp.videoUrl(
      cid: 196018899,
      bvid: 'BV1fK4y1t7hj',
      qn: VideoQuality.high1080.code,
      tryLook: false,
      videoType: VideoType.ugc,
    );
    final item = result.dataOrNull?.dash?.video?.first;
    if (item == null) throw Exception('无法获取视频流');
    return item;
  }

  /// 对单个 CDN 测速，返回字节/微秒；失败返回 null
  ///
  /// [cancelToken] 仅用于外部取消整轮测速；达到 maxSize 时只 cancel 内部 token，
  /// 不会误取消后续 CDN 的测速。
  static Future<double?> measureSpeed(
    String url, {
    CancelToken? cancelToken,
    Duration timeout = _manualTimeout,
    int maxSize = _manualMaxSize,
  }) async {
    if (cancelToken?.isCancelled == true) return null;

    final dio = Dio(
      BaseOptions(
        connectTimeout: timeout,
        receiveTimeout: timeout,
        headers: {
          'user-agent': BrowserUa.pc,
          'referer': HttpString.baseUrl,
        },
      ),
    );

    // Dio 的 count 为累计已接收字节，不是增量
    int downloaded = 0;
    final start = DateTime.now().microsecondsSinceEpoch;
    // 独立 token：到量/超时只停当前请求，不污染外层 cancelToken
    final requestToken = CancelToken();
    if (cancelToken != null) {
      if (cancelToken.isCancelled) {
        requestToken.cancel();
      } else {
        cancelToken.whenCancel.then((_) {
          if (!requestToken.isCancelled) {
            requestToken.cancel();
          }
        });
      }
    }
    var finished = false;
    double? speed;

    void finish() {
      if (finished) return;
      finished = true;
      if (!requestToken.isCancelled) {
        requestToken.cancel();
      }
      final duration = DateTime.now().microsecondsSinceEpoch - start;
      if (downloaded > 0 && duration > 0) {
        speed = downloaded / duration;
      }
    }

    try {
      await dio.get(
        url,
        cancelToken: requestToken,
        onReceiveProgress: (count, total) {
          if (finished || requestToken.isCancelled) return;
          if (cancelToken?.isCancelled == true) {
            if (!requestToken.isCancelled) {
              requestToken.cancel();
            }
            return;
          }
          downloaded = count;
          final duration = DateTime.now().microsecondsSinceEpoch - start;
          if (duration > timeout.inMicroseconds || downloaded >= maxSize) {
            finish();
          }
        },
      );
      if (!finished && downloaded > 0) {
        finish();
      }
    } on DioException catch (e) {
      if (e.type != DioExceptionType.cancel && kDebugMode) {
        debugPrint('CDN speed test error: $e');
      }
      // 外部取消：不记速度
      if (cancelToken?.isCancelled == true) {
        return null;
      }
      if (!finished && downloaded > 0) {
        finish();
      }
    } catch (e) {
      if (kDebugMode) debugPrint('CDN speed test error: $e');
      if (cancelToken?.isCancelled == true) {
        return null;
      }
      if (!finished && downloaded > 0) {
        finish();
      }
    } finally {
      dio.close(force: true);
    }

    return speed;
  }

  static String formatSpeed(double bytesPerUs) =>
      '${bytesPerUs.toStringAsPrecision(3)}MB/s';

  static String formatError(Object error) {
    if (error is DioException) {
      final statusCode = error.response?.statusCode;
      if (statusCode != null && 400 <= statusCode && statusCode < 500) {
        return '此视频可能无法替换为该CDN';
      }
      final msg = error.toString();
      return msg.isEmpty ? '测速失败' : msg;
    }
    final msg = error.toString();
    return msg.isEmpty ? '测速失败' : msg;
  }

  /// 依次测速所有 CDN，返回按速度降序的 (CDN, 速度) 列表
  static Future<List<(CDNService, double)>> testAll(
    BaseItem videoItem, {
    CdnSpeedProgress? onProgress,
    CancelToken? cancelToken,
    Duration timeout = _manualTimeout,
    int maxSize = _manualMaxSize,
  }) async {
    final results = <(CDNService, double)>[];
    for (final item in CDNService.values) {
      if (cancelToken?.isCancelled == true) break;
      try {
        final cdnUrl = VideoUtils.getCdnUrl(
          videoItem.playUrls,
          defaultCDNService: item,
        );
        final speed = await measureSpeed(
          cdnUrl,
          cancelToken: cancelToken,
          timeout: timeout,
          maxSize: maxSize,
        );
        if (cancelToken?.isCancelled == true) break;
        if (speed != null) {
          results.add((item, speed));
          onProgress?.call(item, formatSpeed(speed));
        } else {
          onProgress?.call(item, '测速失败');
        }
      } catch (e) {
        if (cancelToken?.isCancelled == true) break;
        onProgress?.call(item, formatError(e));
      }
    }
    results.sort((a, b) => b.$2.compareTo(a.$2));
    return results;
  }

  /// 卡顿触发：测速并切换到最快 CDN。
  /// 返回值：true=已切换；false=未切换（已是最佳/失败等）
  ///
  /// 调用前应先 [tryReserveAttempt] 占用额度；本方法假定额度已预留。
  /// 不应在未预留时直接调用（内部不再二次校验冷却，避免与预留竞态）。
  static Future<bool> autoSwitchBestCdn({
    BaseItem? sample,
    void Function(CDNService best)? onSwitched,
    void Function(String message)? onMessage,
  }) async {
    // 正常路径：tryReserveAttempt 已通过，且调用方 _autoCdnRunning 防重入。
    // 若仍撞上 _testing，说明有并发漏洞，直接失败（额度已扣，进入冷却）。
    if (_testing) {
      _lastAutoSwitchAt = DateTime.now();
      return false;
    }

    _testing = true;
    try {
      final videoItem = sample ?? await getSampleUrl();
      final results = await testAll(
        videoItem,
        timeout: _autoTimeout,
        maxSize: _autoMaxSize,
      );
      // 无论成败都进入冷却，避免弱网反复测速
      _lastAutoSwitchAt = DateTime.now();
      if (results.isEmpty) {
        onMessage?.call('CDN 测速失败，保持当前线路');
        return false;
      }

      final best = results.first.$1;
      if (best == VideoUtils.cdnService) {
        onMessage?.call('当前已是最佳 CDN');
        return false;
      }

      VideoUtils.cdnService = best;
      await GStorage.setting.put(SettingBoxKey.CDNService, best.name);
      markSuccessfulSwitch();
      onSwitched?.call(best);
      return true;
    } catch (e) {
      if (kDebugMode) debugPrint('autoSwitchBestCdn failed: $e');
      _lastAutoSwitchAt = DateTime.now();
      onMessage?.call('CDN 自动切换失败');
      return false;
    } finally {
      _testing = false;
    }
  }
}
