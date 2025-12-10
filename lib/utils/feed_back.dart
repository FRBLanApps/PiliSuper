import 'package:PiliSuper/utils/storage_pref.dart';
import 'package:flutter/services.dart' show HapticFeedback;

bool enableFeedback = Pref.feedBackEnable;
void feedBack() {
  if (enableFeedback) {
    HapticFeedback.lightImpact();
  }
}
