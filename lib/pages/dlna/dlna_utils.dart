import 'package:dlna_dart/xmlParser.dart' show PositionParser;

/// 从 GetPositionInfo 响应解析可恢复的播放进度（HH:MM:SS），
/// 无有效进度（未实现 / 处于片头 / 解析失败）时返回 null
String? parseSeekTime(String? xml) {
  if (xml == null) return null;
  try {
    final parts = PositionParser(xml).RelTime.split(':');
    if (parts.length != 3) {
      return null;
    }
    final h = int.tryParse(parts[0]);
    final m = int.tryParse(parts[1]);
    final s = double.tryParse(parts[2]);
    if (h == null || m == null || s == null) {
      return null;
    }
    final seconds = h * 3600 + m * 60 + s.truncate();
    if (seconds <= 0) {
      return null;
    }
    return PositionParser.toStr(seconds);
  } catch (_) {
    return null;
  }
}
