#!/usr/bin/env python3
"""Reset the Flutter SDK, then apply this project's patches for one platform."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from build_common import (log_info, log_step, log_success, log_warning,
                          require_command, require_project_root, run_command)

# 所有平台都需要的补丁。顺序和原 patch.ps1 保持一致。
COMMON_PATCHES = [
    "modal_barrier.patch",
    "text_selection.patch",
    "mouse_cursor.patch",
    "image_anim.patch",
    "layout_builder.patch",
    "navigation_drawer.patch",
    "popup_menu.patch",
    "fab.patch",
    "null_safety_for_selectable_region.patch",
    "selectable_region.patch",
    "editable_text.patch",
    "text_field.patch",
    "scroll_position.patch",
    "scrollable.patch",
    "scrollable_gesture.patch",
    "draggable_scrollable_sheet.patch",
    "scaffold.patch",
    "text.patch",
    "text_painter.patch",
    "sliver.patch",
    "refresh_indicator.patch",
]

ANDROID_PATCHES = [
    "bottom_sheet_android.patch",
    "scroll_view.patch",
    "navigator.patch",
]

# 这两项修改的是 PiliSuper 自己的 Dart 源码，必须在项目根目录应用，
# 不能和其余 Flutter SDK patches 一样传给 Flutter SDK 的 git apply。
IOS_PROJECT_PATCHES = [
    "bottom_sheet_ios_piliplus.patch",
    "geetest_ios.patch",
]

IOS_FLUTTER_PATCHES = [
    "scroll_view.patch",
    "bottom_sheet_ios_flutter.patch",
    "navigator.patch",
]

MATERIAL_COMMON_PATCHES = [
    "modal_barrier_material.patch",
    "navigation_drawer.patch",
    "popup_menu.patch",
    "fab.patch",
    "text_field.patch",
    "scaffold.patch",
    "refresh_indicator.patch",
    "tabs.patch",
]
MATERIAL_ANDROID_PATCHES = ["bottom_sheet_android.patch"]
MATERIAL_IOS_PATCHES = ["bottom_sheet_ios_flutter_material.patch"]
MATERIAL_PATCHES = MATERIAL_COMMON_PATCHES

# cupertino_ui 只有 iOS 需要打补丁，其余平台补丁集为空。
CUPERTINO_COMMON_PATCHES: list[str] = []
CUPERTINO_IOS_PATCHES = ["bottom_sheet_ios_flutter.patch"]

# 别看着底下的代码生气就直接塞回主函数里，否则隔壁ci不过。
def apply_project_patch(patch_file: Path, project_root: Path) -> None:
    try:
        run_command(
        ["git", "apply", "--check", str(patch_file), "--ignore-whitespace"],
        cwd=project_root
        )
    except subprocess.CalledProcessError:
        try:
            run_command(
            ["git", "apply", "--reverse", "--check", str(patch_file), "--ignore-whitespace"],
            cwd=project_root
            )
        except subprocess.CalledProcessError:
            raise SystemExit(f"iOS 项目补丁 {patch_file.name}应用失败，且未能回退。")
        else:
            log_warning(f"iOS 项目补丁 {patch_file.name} 应用失败，已忽略")
    else:
        run_command(
        ["git", "apply", str(patch_file), "--ignore-whitespace"],
        cwd=project_root
        )
        log_success(f"Applied project patch: {patch_file.name}")

def pub_cache_dir() -> Path:
    configured = os.environ.get("PUB_CACHE")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Pub" / "Cache"
    return Path.home() / ".pub-cache"


def material_ui_dir(cache_dir: Path) -> Path | None:
    return _latest_package_dir(cache_dir, "material_ui-*")


def cupertino_ui_dir(cache_dir: Path) -> Path | None:
    return _latest_package_dir(cache_dir, "cupertino_ui-*")


def _latest_package_dir(cache_dir: Path, pattern: str) -> Path | None:
    candidates = sorted(
        path
        for path in (cache_dir / "hosted" / "pub.dev").glob(pattern)
        if path.is_dir()
    )
    return candidates[-1] if candidates else None


def should_reset_flutter_sdk(platform: str) -> bool:
    return platform in ("android", "linux", "all")


def material_patch_names(platform: str) -> list[str]:
    if platform == "android":
        return [*MATERIAL_COMMON_PATCHES, *MATERIAL_ANDROID_PATCHES]
    if platform == "ios":
        return [*MATERIAL_COMMON_PATCHES, *MATERIAL_IOS_PATCHES]
    return list(MATERIAL_COMMON_PATCHES)


def cupertino_patch_names(platform: str) -> list[str]:
    if platform in ("ios", "all"):
        return [*CUPERTINO_COMMON_PATCHES, *CUPERTINO_IOS_PATCHES]
    return list(CUPERTINO_COMMON_PATCHES)


def apply_sdk_patches(
    patch_names: list[str], patch_dir: Path, flutter_root: Path
) -> None:
    applied_names: set[str] = set()
    for patch_name in patch_names:
        if patch_name in applied_names:
            continue
        applied_names.add(patch_name)
        patch_file = patch_dir / patch_name
        if not patch_file.is_file():
            raise FileNotFoundError(f"Flutter patch not found: {patch_file}")
        log_step(f"Apply {patch_name}")
        run_command(
            ["git", "apply", str(patch_file.resolve()), "--ignore-whitespace"],
            cwd=flutter_root,
        )
        log_success(f"Applied: {patch_name}")


def normalize_patch_line_endings(patch_dir: Path) -> None:
    # 与上游 patch.ps1 对齐：Windows 检出可能带 CRLF，应用前统一转成 LF，
    # 否则对 pub cache 里的 material_ui 包执行 git apply 会失败。
    for patch_file in sorted(patch_dir.glob("*.patch")):
        raw = patch_file.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if normalized != raw:
            patch_file.write_bytes(normalized)


def apply_material_patches(platform: str, patch_dir: Path, project_root: Path) -> None:
    cache_dir = pub_cache_dir()
    existing = material_ui_dir(cache_dir)
    if existing is not None:
        shutil.rmtree(existing)

    log_step("Fetch material_ui package")
    run_command(["flutter", "pub", "get"], cwd=project_root)
    package_dir = material_ui_dir(cache_dir)
    if package_dir is None:
        raise SystemExit("material_ui package not found in pub cache")

    log_info(f"material_ui dir: {package_dir}")

    material_dir = patch_dir / "material"
    normalize_patch_line_endings(material_dir)
    for patch_name in material_patch_names(platform):
        patch_file = material_dir / patch_name
        log_step(f"Apply material_ui patch {patch_name}")
        run_command(["git", "apply", str(patch_file.resolve())], cwd=package_dir)
        log_success(f"Applied material_ui patch: {patch_name}")


def apply_cupertino_patches(platform: str, patch_dir: Path) -> None:
    package_dir = cupertino_ui_dir(pub_cache_dir())
    if package_dir is None:
        raise SystemExit("cupertino_ui package not found in pub cache")

    log_info(f"cupertino_ui dir: {package_dir}")

    cupertino_dir = patch_dir / "cupertino"
    normalize_patch_line_endings(cupertino_dir)
    for patch_name in cupertino_patch_names(platform):
        patch_file = cupertino_dir / patch_name
        log_step(f"Apply cupertino_ui patch {patch_name}")
        run_command(["git", "apply", str(patch_file.resolve())], cwd=package_dir)
        log_success(f"Applied cupertino_ui patch: {patch_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "platform",
        choices=["android", "ios", "macos", "windows", "linux", "all"],
        help="要应用对应平台补丁的平台；all 会包含 Android 和 iOS 补丁。",
    )
    args = parser.parse_args()
    require_project_root()

    needs_android_patch = args.platform in ("android", "all")
    needs_ios_patch = args.platform in ("ios", "all")
    project_root = Path.cwd()
    patch_dir = project_root / "tool/patches"
    #创建Flutter SDK补丁列表，先公共补丁，后平台特定补丁
    patch_names = list(COMMON_PATCHES)
    if needs_android_patch:
        patch_names.extend(ANDROID_PATCHES)
    if needs_ios_patch:
        patch_names.extend(IOS_FLUTTER_PATCHES)

    # 1. 按上游 patch.ps1 将 iOS 上的项目源码补丁在找Flutter SDK前在项目根目录应用。
    if needs_ios_patch:
        for patch_name in IOS_PROJECT_PATCHES:
            patch_file = patch_dir / patch_name
            log_step(f"Apply project patch {patch_name}")
            apply_project_patch(patch_file, project_root)

    # 2. 找到位于 <SDK>/bin/flutter 的 Flutter SDK。
    require_command("flutter", "请安装 Flutter，或将其加入 PATH")
    flutter = shutil.which("flutter")
    if flutter is None:  # require_command 已处理；保留这一行供类型检查与防御性处理。
        raise SystemExit(1)
    flutter_root = Path(flutter).resolve().parent.parent

    # 3. Configure patching identity and reset only platforms that need it.
    run_command(["git", "config", "user.name", "ci"], cwd=flutter_root)
    run_command(["git", "config", "user.email", "ci@example.com"], cwd=flutter_root)
    if should_reset_flutter_sdk(args.platform):
        log_step("Reset Flutter SDK")
        run_command(["git", "reset", "--hard", "HEAD"], cwd=flutter_root)

    # 4. Apply SDK patches. A failed patch aborts the script like patch.ps1.
    apply_sdk_patches(patch_names, patch_dir, flutter_root)

    apply_material_patches(args.platform, patch_dir, project_root)

    apply_cupertino_patches(args.platform, patch_dir)


if __name__ == "__main__":
    main()
