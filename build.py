#!/usr/bin/env python3
"""
Flutter 多平台构建脚本
移植自 lib/scripts/build.ps1

用法:
  python build.py android
  python build.py android --pkg-id com.myfork.app --app-name my_fork --sign
  python build.py linux --linux-targets tar.gz deb rpm arch appimage
  python build.py all --pkg-id com.myfork.app --output dist/
  python build.py android -- --obfuscate --split-debug-info=./debug
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import io
import json
import logging
import os
import platform as platform_module
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.request import urlopen

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install as install_rich_traceback
except ImportError:
    Console = None
    RichHandler = None
    install_rich_traceback = None

# Windows stdout UTF-8（▶ 等字符在 cp1252 下无法输出）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


@dataclass
class VersionInfo:
    version_name: str
    version_code: int
    version_full: str


BUILDABLE_PLATFORMS = ("android", "ios", "macos", "windows", "linux")


@dataclass(frozen=True)
class BuildOptions:
    platform: str
    pkg_id: str
    original_pkg_id: str
    app_name: str
    original_app_name: str
    skip_rename: bool
    repo: str
    original_repo: str
    dart_define_from_file: Path | None
    dart_define: tuple[str, ...]
    arch: str | None
    version: str | None
    no_prebuild: bool
    no_split: bool
    sign: bool
    keystore_file: Path | None
    keystore_base64: str | None
    key_alias: str | None
    key_password: str | None
    store_password: str | None
    clean_keys: bool
    installer: bool
    linux_targets: tuple[str, ...]
    output: Path
    output_prefix: str
    apply_patches: bool
    no_pub_get: bool
    extra_build_args: tuple[str, ...]

    @classmethod
    def from_namespace(
        cls,
        namespace: argparse.Namespace,
        extra_build_args: Sequence[str],
    ) -> "BuildOptions":
        output_prefix = namespace.output_prefix
        if not output_prefix and Path("pubspec.yaml").exists():
            output_prefix = get_pubspec_name()

        return cls(
            platform=namespace.platform,
            pkg_id=namespace.pkg_id,
            original_pkg_id=namespace.original_pkg_id,
            app_name=namespace.app_name,
            original_app_name=namespace.original_app_name,
            skip_rename=namespace.skip_rename,
            repo=namespace.repo,
            original_repo=namespace.original_repo,
            dart_define_from_file=(
                Path(namespace.dart_define_from_file)
                if namespace.dart_define_from_file
                else None
            ),
            dart_define=tuple(namespace.dart_define or ()),
            arch=namespace.arch,
            version=namespace.version,
            no_prebuild=namespace.no_prebuild,
            no_split=namespace.no_split,
            sign=namespace.sign,
            keystore_file=(
                Path(namespace.keystore_file) if namespace.keystore_file else None
            ),
            keystore_base64=namespace.keystore_base64,
            key_alias=namespace.key_alias,
            key_password=namespace.key_password,
            store_password=namespace.store_password,
            clean_keys=namespace.clean_keys,
            installer=namespace.installer,
            linux_targets=tuple(namespace.linux_targets or ()),
            output=Path(namespace.output),
            output_prefix=output_prefix,
            apply_patches=namespace.apply_patches,
            no_pub_get=namespace.no_pub_get,
            extra_build_args=tuple(extra_build_args),
        )

    @property
    def target_platforms(self) -> tuple[str, ...]:
        if self.platform == "all":
            return BUILDABLE_PLATFORMS
        return (self.platform,)

    @property
    def prebuild_platform(self) -> str:
        if self.platform == "all":
            return "other"
        return self.platform


@dataclass(frozen=True)
class BuildContext:
    options: BuildOptions
    version_info: VersionInfo
    output_dir: Path

    @classmethod
    def create(cls, options: BuildOptions, version_info: VersionInfo) -> "BuildContext":
        return cls(
            options=options,
            version_info=version_info,
            output_dir=ensure_output_dir(options.output),
        )

    @property
    def version(self) -> str:
        return self.version_info.version_full

    @property
    def prefix(self) -> str:
        return self.options.output_prefix

    def platform_output_stem(self, platform_name: str, *parts: str) -> Path:
        stem = "_".join(
            part for part in (self.prefix, platform_name, self.version, *parts) if part
        )
        return self.output_dir / stem

    def platform_output_path(
        self,
        platform_name: str,
        *parts: str,
        suffix: str,
    ) -> Path:
        return Path(f"{self.platform_output_stem(platform_name, *parts)}{suffix}")


PlatformBuilder = Callable[[BuildContext], None]


def configure_logging() -> tuple[logging.Logger, Any | None]:
    logger = logging.getLogger("pilisuper.build")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if RichHandler is not None and Console is not None:
        console: Any | None = Console(stderr=True, soft_wrap=True)
        if install_rich_traceback is not None:
            install_rich_traceback(show_locals=False)
        handler: logging.Handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_time=False,
            show_level=False,
            show_path=False,
        )
    else:
        console = None
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger, console


LOGGER, RICH_CONSOLE = configure_logging()
SKIP_RENAME_DIR_NAMES = {".git", ".dart_tool", "build", "Pods", "ephemeral"}


def _format_log_message(label: str, message: str, style: str) -> str:
    if RICH_CONSOLE is not None:
        return f"[{style}]{label:<5}[/] {message}"
    return f"{label:<5} {message}"


def log_info(message: str) -> None:
    LOGGER.info(_format_log_message("INFO", message, "cyan"))


def log_success(message: str) -> None:
    LOGGER.info(_format_log_message("OK", message, "green"))


def log_warning(message: str) -> None:
    LOGGER.warning(_format_log_message("WARN", message, "yellow"))


def log_error(message: str) -> None:
    LOGGER.error(_format_log_message("ERROR", message, "red"))


def log_step(message: str) -> None:
    if RICH_CONSOLE is not None:
        RICH_CONSOLE.rule(f"[bold cyan]{message}[/bold cyan]")
        return
    LOGGER.info("")
    LOGGER.info(_format_log_message("STEP", message, "cyan"))


# ══════════════════════════════════════════════════════════════════
#  Shell 工具
# ══════════════════════════════════════════════════════════════════

IS_WINDOWS = platform_module.system() == "Windows"


def _resolve_command(command: Sequence[str]) -> list[str]:
    """
    Windows 上 flutter / dart 等工具是 .bat 文件，
    subprocess shell=False 找不到，用 shutil.which 解析完整路径。
    """
    command_parts = [str(part) for part in command]
    if not IS_WINDOWS:
        return command_parts
    resolved = shutil.which(command_parts[0])
    if resolved:
        command_parts = [resolved] + command_parts[1:]
    return command_parts


def run_command(
    command: Sequence[str],
    cwd: str | Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if isinstance(command, str):
        raise TypeError(
            "run_command() expects a sequence of arguments. "
            "Use run_shell_command() for string commands."
        )
    merged_env = {**os.environ, **(env or {})}
    command_parts = list(command)
    command_parts = _resolve_command(command_parts)
    if not capture_output:
        log_info("$ " + " ".join(command_parts))
    return subprocess.run(
        command_parts,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=merged_env,
    )


def run_shell_command(
    command: str,
    cwd: str | Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = {**os.environ, **(env or {})}
    if not capture_output:
        log_info("$ " + command)
    return subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=merged_env,
    )


def get_git_output(args: Sequence[str]) -> str:
    try:
        return run_command(["git", *args], capture_output=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def require_command(tool_name: str, hint: str = "") -> None:
    if not shutil.which(tool_name):
        log_error(f"找不到 {tool_name}。{hint}")
        sys.exit(1)


def download_file(url: str, destination: Path) -> None:
    log_info(f"下载: {url}")
    with urlopen(url, timeout=60) as response, destination.open("wb") as file_obj:
        shutil.copyfileobj(response, file_obj)


# ══════════════════════════════════════════════════════════════════
#  pubspec 读写
# ══════════════════════════════════════════════════════════════════


def read_pubspec_text() -> str:
    return Path("pubspec.yaml").read_text(encoding="utf-8")


def get_pubspec_name() -> str:
    match = re.search(r"^name:\s+(\S+)", read_pubspec_text(), re.MULTILINE)
    return match.group(1) if match else "app"


def get_pubspec_version_base() -> str:
    match = re.search(r"^version:\s*([\d.]+)", read_pubspec_text(), re.MULTILINE)
    return match.group(1) if match else "0.0.0"


# ══════════════════════════════════════════════════════════════════
#  Prebuild（移植 build.ps1）
# ══════════════════════════════════════════════════════════════════


def run_prebuild(platform_name: str) -> VersionInfo:
    log_step("Prebuild（移植 build.ps1）")

    lines = read_pubspec_text().splitlines()
    version_name = None
    version_line_index = None
    for index, line in enumerate(lines):
        match = re.match(r"^\s*version:\s*([\d.]+)", line)
        if match:
            version_name = match.group(1)
            version_line_index = index
            break

    if version_name is None:
        log_error("pubspec.yaml 中未找到 version 字段")
        sys.exit(1)

    version_code_str = get_git_output(["rev-list", "--count", "HEAD"])
    version_code = int(version_code_str) if version_code_str.isdigit() else 0
    commit_hash = get_git_output(["rev-parse", "HEAD"]) or "unknown"

    display_version = version_name
    if platform_name == "android":
        display_version = f"{version_name}-{commit_hash[:9]}"

    version_full = f"{display_version}+{version_code}"
    lines[version_line_index] = f"version: {version_full}"
    Path("pubspec.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log_success(f"pubspec.yaml version → {version_full}")

    Path("pili_release.json").write_text(
        json.dumps(
            {
                "pili.name": display_version,
                "pili.code": version_code,
                "pili.hash": commit_hash,
                "pili.time": int(time.time()),
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    log_success("pili_release.json 已生成")
    return VersionInfo(
        version_name=display_version,
        version_code=version_code,
        version_full=version_full,
    )


# ══════════════════════════════════════════════════════════════════
#  包名替换
#  ① sed patch  — pubspec name 字段 + Dart import 路径
#  ② rename CLI — Android applicationId / iOS Bundle ID / 显示名
# ══════════════════════════════════════════════════════════════════


def replace_text_in_files(old: str, new: str, globs: list[str]) -> None:
    import glob as _glob

    for pattern in globs:
        for file_name in _glob.glob(pattern, recursive=True):
            file_path = Path(file_name)
            if not file_path.is_file() or any(
                part in SKIP_RENAME_DIR_NAMES for part in file_path.parts
            ):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                if old in content:
                    file_path.write_text(content.replace(old, new), encoding="utf-8")
                    log_info(f"  sed: {file_name}")
            except Exception as exc:
                log_warning(f"  跳过 {file_name}: {exc}")


def rename_with_search_replace(options: BuildOptions) -> None:
    """
    sed 负责：
      • pubspec.yaml  name: 字段
      • Dart 文件中  package:old_name/ → package:new_name/
      • 原生代码中   com/old/pkg 目录路径形式
      • 仓库 URL    github.com/old/repo → github.com/new/repo
    rename CLI 负责：
      • Android applicationId（build.gradle / AndroidManifest）
      • iOS/macOS Bundle Identifier（plist / pbxproj）
      • 显示名（android:label / CFBundleDisplayName）
    """
    orig_name = options.original_app_name
    new_name = options.app_name
    orig_pkg = options.original_pkg_id
    new_pkg = options.pkg_id

    dart_globs = ["**/*.dart", "pubspec.yaml"]
    native_globs = [
        "android/**/*.kt",
        "android/**/*.java",
        "android/**/*.xml",
        "android/**/*.gradle",
        "android/**/*.gradle.kts",
        "android/**/*.properties",
        "ios/**/*.plist",
        "ios/**/*.pbxproj",
        "macos/**/*.plist",
        "macos/**/*.pbxproj",
        "linux/**/*.cmake",
        "linux/**/*.cc",
        "windows/runner/*.rc",
        "windows/runner/*.h",
        "windows/runner/*.cpp",
        "windows/CMakeLists.txt",
        "assets/linux/com.example.piliplus.desktop",
        "assets/linux/DEBIAN/*",
    ]

    if new_name and orig_name and new_name != orig_name:
        log_step(f"sed patch: pubspec name  {orig_name} → {new_name}")
        # Dart import 路径
        replace_text_in_files(
            f"package:{orig_name}/", f"package:{new_name}/", dart_globs
        )
        # pubspec.yaml name: 字段
        content = read_pubspec_text()
        content = re.sub(
            r"^(name:\s+)" + re.escape(orig_name),
            r"\g<1>" + new_name,
            content,
            flags=re.MULTILINE,
        )
        Path("pubspec.yaml").write_text(content, encoding="utf-8")
        log_success("pubspec.yaml name 字段已更新")

    if new_pkg and orig_pkg and new_pkg != orig_pkg:
        old_path = orig_pkg.replace(".", "/")
        new_path = new_pkg.replace(".", "/")
        if old_path != new_path:
            log_step(f"sed patch: 包路径  {old_path} → {new_path}")
            replace_text_in_files(old_path, new_path, native_globs)

    # ── 仓库 URL 替换 ──
    if options.repo and options.original_repo and options.repo != options.original_repo:
        log_step(f"sed patch: 仓库 URL  {options.original_repo} → {options.repo}")
        repo_globs = [
            "assets/linux/DEBIAN/*",
            "lib/**/*.dart",
            "windows/packaging/exe/make_config.yaml",
        ]
        replace_text_in_files(options.original_repo, options.repo, repo_globs)


def rename_with_cli(options: BuildOptions) -> None:
    if not options.pkg_id and not options.app_name:
        return
    log_step("rename CLI（Bundle ID / 显示名）")
    require_command("rename", "请先运行：dart pub global activate rename")
    if options.pkg_id:
        log_info(f"setBundleId → {options.pkg_id}")
        run_command(["rename", "setBundleId", "--value", options.pkg_id])
    if options.app_name:
        log_info(f"setAppName → {options.app_name}")
        run_command(["rename", "setAppName", "--value", options.app_name])


def apply_project_rename(options: BuildOptions) -> None:
    if options.skip_rename:
        return
    rename_with_search_replace(options)
    rename_with_cli(options)


# ══════════════════════════════════════════════════════════════════
#  Git Tools
# ══════════════════════════════════════════════════════════════════


def stash_worktree_changes(cwd: str | None) -> bool:
    result = run_command(
        ["git", "stash", "push", "--include-untracked", "-m", "build.py-temp"],
        cwd=cwd,
        check=False,
        capture_output=True,
    )
    stash_output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        log_warning("git stash 失败，继续尝试应用补丁")
        return False
    return "No local changes to save" not in stash_output


def restore_stashed_changes(cwd: str | None, has_stash: bool) -> None:
    if not has_stash:
        return
    result = run_command(
        ["git", "stash", "pop"],
        cwd=cwd,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        log_warning("git stash pop 失败，请手动检查 Flutter SDK 仓库状态")


def abort_git_sequence(operation: str, cwd: str | None) -> None:
    run_command(
        ["git", operation, "--abort"],
        cwd=cwd,
        check=False,
        capture_output=True,
    )


def configure_git_identity(cwd: str | None) -> None:
    run_command(["git", "config", "user.name", "ci"], cwd=cwd)
    run_command(["git", "config", "user.email", "ci@example.com"], cwd=cwd)


def apply_git_history_edit(
    operation: str,
    commit_hash: str,
    cwd: str | None,
    finished_message: str,
    bad_message: str,
) -> None:
    has_stash = stash_worktree_changes(cwd)
    try:
        configure_git_identity(cwd)
        run_command(["git", operation, commit_hash, "--no-edit"], cwd=cwd)
    except subprocess.CalledProcessError:
        abort_git_sequence(operation, cwd)
        log_warning(bad_message)
    else:
        run_command(["git", "reset", "--soft", "HEAD~1"], cwd=cwd)
        log_success(finished_message)
    finally:
        restore_stashed_changes(cwd, has_stash)


def apply_git_revert(
    commit_hash: str,
    cwd: str | None = None,
    finished_message: str = "已回滚",
    bad_message: str = "回滚失败",
) -> None:
    apply_git_history_edit(
        "revert",
        commit_hash,
        cwd,
        finished_message,
        bad_message,
    )


def apply_git_cherry_pick(
    commit_hash: str,
    cwd: str | None = None,
    finished_message: str = "已应用 cherry-pick",
    bad_message: str = "应用 cherry-pick 失败",
) -> None:
    apply_git_history_edit(
        "cherry-pick",
        commit_hash,
        cwd,
        finished_message,
        bad_message,
    )


def apply_git_patch(
    patch_file: str | Path,
    cwd: str | None = None,
    notfound_message: str = "patch 不存在，跳过",
    finished_message: str = "已应用 patch",
    bad_message: str = "应用 patch 失败",
) -> None:
    patch_file = Path(patch_file).resolve()
    if not patch_file.exists():
        log_warning(notfound_message)
        return
    try:
        run_command(["git", "apply", str(patch_file), "--ignore-whitespace"], cwd=cwd)
        log_success(finished_message)
    except subprocess.CalledProcessError:
        log_warning(bad_message)

# ══════════════════════════════════════════════════════════════════
#  Flutter patches & pub get
# ══════════════════════════════════════════════════════════════════


def find_flutter_root() -> str | None:
    flutter_binary = shutil.which("flutter")
    return str(Path(flutter_binary).parent.parent) if flutter_binary else None


@dataclass(frozen=True)
class FlutterPatchAction:
    kind: str
    target: str
    success_message: str
    failure_message: str
    step_message: str = ""


def make_flutter_patch_action(name: str) -> FlutterPatchAction:
    return FlutterPatchAction(
        kind="patch",
        target=name,
        success_message=f"Patch OK: {name}",
        failure_message=f"Patch 应用失败（已忽略）: {name}",
    )


FLUTTER_PATCH_ACTION_PRIORITY = {"cherry-pick": 0, "revert": 1, "patch": 2}
FLUTTER_PATCHES_DIR = Path("lib/scripts")
TOOLTIP_FIX_COMMIT = "56956c33ef102ac0b5fc46b62bd2dd9f50a86616"
NEW_OVERSCROLL_INDICATOR_COMMIT = "362b1de29974ffc1ed6faa826e1df870d7bec75f"

TOOLTIP_FIX_ACTION = FlutterPatchAction(
    kind="cherry-pick",
    target=TOOLTIP_FIX_COMMIT,
    success_message="Add RawTooltip.ignorePointer 应用完成",
    failure_message="Add RawTooltip.ignorePointer 应用失败（已忽略）",
    step_message=(
        "checkout Add RawTooltip.ignorePointer commit "
        f"({TOOLTIP_FIX_COMMIT[:9]}…)"
    ),
)
OVERSCROLL_INDICATOR_REVERT_ACTION = FlutterPatchAction(
    kind="revert",
    target=NEW_OVERSCROLL_INDICATOR_COMMIT,
    success_message="overscroll indicator revert 完成",
    failure_message="overscroll indicator revert 失败（已忽略）",
    step_message=(
        "revert overscroll indicator commit "
        f"({NEW_OVERSCROLL_INDICATOR_COMMIT[:9]}…)"
    ),
)

COMMON_FLUTTER_PATCH_ACTIONS = (
    make_flutter_patch_action("modal_barrier.patch"),
    make_flutter_patch_action("text_selection.patch"),
    make_flutter_patch_action("mouse_cursor.patch"),
)
PLATFORM_FLUTTER_PATCH_ACTIONS = {
    "android": (
        OVERSCROLL_INDICATOR_REVERT_ACTION,
        make_flutter_patch_action("bottom_sheet.patch"),
        make_flutter_patch_action("scroll_view.patch"),
    ),
    "ios": (make_flutter_patch_action("scroll_view.patch"),),
    "linux": (TOOLTIP_FIX_ACTION,),
    "macos": (TOOLTIP_FIX_ACTION,),
    "windows": (TOOLTIP_FIX_ACTION,),
}


def dedupe_flutter_patch_actions(
    actions: Sequence[FlutterPatchAction],
) -> tuple[FlutterPatchAction, ...]:
    seen: set[tuple[str, str]] = set()
    unique_actions: list[FlutterPatchAction] = []
    for action in actions:
        key = (action.kind, action.target)
        if key in seen:
            continue
        seen.add(key)
        unique_actions.append(action)
    return tuple(
        sorted(
            unique_actions,
            key=lambda action: FLUTTER_PATCH_ACTION_PRIORITY[action.kind],
        )
    )


def build_flutter_patch_actions(platform_name: str) -> tuple[FlutterPatchAction, ...]:
    normalized_platform = platform_name.strip().lower()
    actions = list(COMMON_FLUTTER_PATCH_ACTIONS)

    if normalized_platform == "all":
        target_platforms = tuple(PLATFORM_FLUTTER_PATCH_ACTIONS)
    elif normalized_platform in PLATFORM_FLUTTER_PATCH_ACTIONS:
        target_platforms = (normalized_platform,)
    else:
        target_platforms = ()

    for target_platform in target_platforms:
        actions.extend(PLATFORM_FLUTTER_PATCH_ACTIONS[target_platform])

    return dedupe_flutter_patch_actions(actions)


def apply_flutter_patch_action(root: str, action: FlutterPatchAction) -> None:
    if action.step_message:
        log_step(action.step_message)

    if action.kind == "revert":
        apply_git_revert(
            action.target,
            cwd=root,
            finished_message=action.success_message,
            bad_message=action.failure_message,
        )
        return

    if action.kind == "cherry-pick":
        apply_git_cherry_pick(
            action.target,
            cwd=root,
            finished_message=action.success_message,
            bad_message=action.failure_message,
        )
        return

    if action.kind == "patch":
        apply_git_patch(
            FLUTTER_PATCHES_DIR / action.target,
            cwd=root,
            notfound_message=f"patch 不存在，跳过: {action.target}",
            finished_message=action.success_message,
            bad_message=action.failure_message,
        )
        return

    raise ValueError(f"Unknown Flutter patch action: {action.kind}")


def apply_flutter_patches(root: str, platform_name: str = "") -> None:
    log_step("应用 Flutter patches")
    for action in build_flutter_patch_actions(platform_name):
        apply_flutter_patch_action(root, action)

def run_common_setup(options: BuildOptions) -> str | None:
    flutter_root_dir = find_flutter_root()
    if options.apply_patches and flutter_root_dir:
        apply_flutter_patches(flutter_root_dir, platform_name=options.platform)
    if not options.no_pub_get:
        log_step("flutter pub get")
        run_command(["flutter", "pub", "get"])
    return flutter_root_dir


# ══════════════════════════════════════════════════════════════════
#  构建参数组装
# ══════════════════════════════════════════════════════════════════


def build_dart_define_args(options: BuildOptions) -> list[str]:
    dart_define_args: list[str] = []
    if options.dart_define_from_file and options.dart_define_from_file.exists():
        dart_define_args += [
            "--dart-define-from-file",
            str(options.dart_define_from_file),
        ]
    for dart_define in options.dart_define:
        dart_define_args += ["--dart-define", dart_define]
    return dart_define_args


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_flutter_build_command(
    target: str,
    options: BuildOptions,
    extra_args: Sequence[str] = (),
) -> list[str]:
    return [
        "flutter",
        "build",
        target,
        "--release",
        *extra_args,
        *build_dart_define_args(options),
        *options.extra_build_args,
    ]


def resolve_version_info(options: BuildOptions) -> VersionInfo:
    if options.no_prebuild:
        version = options.version or get_pubspec_version_base()
        return VersionInfo(
            version_name=version,
            version_code=0,
            version_full=version,
        )

    version_info = run_prebuild(options.prebuild_platform)
    if options.version:
        version_info.version_full = options.version
    return version_info


# ══════════════════════════════════════════════════════════════════
#  Android 签名
# ══════════════════════════════════════════════════════════════════


def configure_android_signing(options: BuildOptions) -> bool:
    if not options.sign:
        return False
    log_step("配置 Android 签名")

    key_jks = Path("android/app/key.jks")
    key_prop = Path("android/key.properties")

    if options.keystore_base64:
        import base64

        key_jks.write_bytes(base64.b64decode(options.keystore_base64))
        log_success("keystore 已从 base64 写入")
    elif options.keystore_file:
        shutil.copy2(options.keystore_file, key_jks)
        log_success(f"keystore 已复制: {options.keystore_file}")
    elif key_jks.exists():
        log_success("使用已有 android/app/key.jks")
    else:
        log_warning("--sign 已设置，但无 keystore，将用 debug 签名")
        return False

    if not options.key_alias:
        log_error("签名需要 --key-alias")
        sys.exit(1)
    if not options.key_password:
        log_error("签名需要 --key-password")
        sys.exit(1)

    key_prop.write_text(
        f"storeFile=key.jks\nstorePassword={options.store_password or options.key_password}\n"
        f"keyAlias={options.key_alias}\nkeyPassword={options.key_password}\n",
        encoding="utf-8",
    )
    log_success("android/key.properties 已写入")
    return True


def cleanup_android_signing_files() -> None:
    for file_path in [Path("android/app/key.jks"), Path("android/key.properties")]:
        if file_path.exists():
            file_path.unlink()
            log_info(f"已清理: {file_path}")


# ══════════════════════════════════════════════════════════════════
#  Android
# ══════════════════════════════════════════════════════════════════


def build_android(context: BuildContext) -> None:
    log_step("构建 Android")
    options = context.options
    signed = configure_android_signing(options)
    try:
        run_command(
            create_flutter_build_command(
                "apk",
                options,
                [
                    "--pub",
                    *([] if options.no_split else ["--split-per-abi"]),
                ],
            )
        )
    finally:
        if signed and options.clean_keys:
            cleanup_android_signing_files()

    log_step("重命名 APK")
    apk_dir = Path("build/app/outputs/flutter-apk")
    apks = list(apk_dir.glob("app-*-release.apk")) or list(
        apk_dir.glob("app-release.apk")
    )
    for apk in apks:
        match = re.search(r"app-(.+)-release\.apk", apk.name)
        abi = match.group(1) if match else "universal"
        destination = context.platform_output_path("android", abi, suffix=".apk")
        shutil.copy2(apk, destination)
        log_success(f"输出: {destination}")


# ══════════════════════════════════════════════════════════════════
#  iOS
# ══════════════════════════════════════════════════════════════════


def build_ios(context: BuildContext) -> None:
    if platform_module.system() != "Darwin":
        log_error("iOS 构建只能在 macOS")
        sys.exit(1)
    log_step("构建 iOS")
    run_command(
        create_flutter_build_command("ios", context.options, ["--no-codesign"])
    )

    log_step("打包 IPA")
    ipa_name = context.platform_output_path("ios", suffix=".ipa").name
    payload = Path("Payload")
    if payload.is_symlink() or payload.exists():
        payload.unlink() if payload.is_symlink() else shutil.rmtree(payload)
    payload.symlink_to("build/ios/iphoneos")
    run_shell_command(
        'find Payload/Runner.app/Frameworks -type d -name "*.framework" '
        "-exec codesign --force --sign - --preserve-metadata=identifier,entitlements {} \\;",
        check=False,
    )
    run_shell_command(f"zip -r9 {ipa_name} Payload/Runner.app")
    output_path = context.output_dir / ipa_name
    shutil.move(ipa_name, output_path)
    log_success(f"输出: {output_path}")


# ══════════════════════════════════════════════════════════════════
#  macOS
# ══════════════════════════════════════════════════════════════════


def build_macos(context: BuildContext) -> None:
    if platform_module.system() != "Darwin":
        log_error("macOS 构建只能在 macOS")
        sys.exit(1)
    log_step("构建 macOS")
    run_command(create_flutter_build_command("macos", context.options))

    app = next(Path("build/macos/Build/Products/Release").glob("*.app"), None)
    if not app:
        log_error("未找到 .app")
        sys.exit(1)

    if shutil.which("create-dmg"):
        run_shell_command(f'create-dmg "{app}" || true', check=False)
        dmgs = list(Path(".").glob("*.dmg"))
        if dmgs:
            destination = context.platform_output_path("macos", suffix=".dmg")
            shutil.move(str(dmgs[0]), destination)
            log_success(f"输出: {destination}")
            return
    log_warning("create-dmg 未安装，fallback zip。npm i -g create-dmg")
    destination = context.platform_output_path("macos", suffix=".zip")
    run_shell_command(f'zip -r9 "{destination}" "{app}"')
    log_success(f"输出（zip）: {destination}")


# ══════════════════════════════════════════════════════════════════
#  Windows
# ══════════════════════════════════════════════════════════════════


def build_windows(context: BuildContext) -> None:
    log_step("构建 Windows")
    options = context.options

    if options.installer and shutil.which("fastforge"):
        dart_define_arg = (
            f"dart-define-from-file={options.dart_define_from_file}"
            if options.dart_define_from_file and options.dart_define_from_file.exists()
            else ""
        )
        run_command(
            [
                "fastforge",
                "package",
                "--platform",
                "windows",
                "--targets",
                "exe",
                *( ["--flutter-build-args", dart_define_arg] if dart_define_arg else []),
                *options.extra_build_args,
            ]
        )
        for exe in Path("dist").rglob("*.exe"):
            destination = context.platform_output_path(
                "windows", "x64", "setup", suffix=".exe"
            )
            shutil.copy2(exe, destination)
            log_success(f"输出 (installer): {destination}")
    else:
        if options.installer:
            log_warning("fastforge 未找到，跳过 installer")
        run_command(create_flutter_build_command("windows", options))

    bundle = Path("build/windows/x64/runner/Release")
    if bundle.exists():
        base = context.platform_output_stem("windows", "x64", "portable")
        shutil.make_archive(str(base), "zip", bundle)
        log_success(f"输出 (portable): {base}.zip")


# ══════════════════════════════════════════════════════════════════
#  Linux 各打包格式
# ══════════════════════════════════════════════════════════════════


def resolve_package_name(options: BuildOptions) -> str:
    return options.app_name or get_pubspec_name()


def get_linux_desktop_file() -> Path | None:
    assets_linux = Path("assets/linux")
    if not assets_linux.exists():
        return None
    return next(assets_linux.glob("*.desktop"), None)


def read_desktop_entry_value(desktop_file: Path | None, key: str) -> str | None:
    if desktop_file is None or not desktop_file.exists():
        return None
    pattern = re.compile(rf"^{re.escape(key)}=(.+)$", re.MULTILINE)
    match = pattern.search(desktop_file.read_text(encoding="utf-8"))
    if not match:
        return None
    return match.group(1).strip()


def resolve_linux_binary_name(bundle: Path, desktop_file: Path | None, app_name: str) -> str:
    exec_value = read_desktop_entry_value(desktop_file, "Exec")
    if exec_value:
        exec_name = exec_value.split()[0].strip()
        if exec_name and (bundle / exec_name).exists():
            return exec_name

    candidate = bundle / app_name
    if candidate.exists():
        return app_name

    for file_path in bundle.iterdir():
        if not file_path.is_file():
            continue
        if file_path.name.endswith((".so", ".json", ".dat", ".pak")):
            continue
        return file_path.name

    return app_name


def resolve_linux_icon_name(desktop_file: Path | None, app_name: str) -> str:
    return read_desktop_entry_value(desktop_file, "Icon") or app_name


def package_tar_gz(prefix: str, version: str, arch: str, bundle: Path, output_dir: Path) -> None:
    output_file = output_dir / f"{prefix}_linux_{version}_{arch}.tar.gz"
    run_shell_command(f"tar -zcf {output_file} -C {bundle} .")
    log_success(f"输出: {output_file}")


def package_tar_zst(
    prefix: str,
    version: str,
    arch: str,
    bundle: Path,
    output_dir: Path,
) -> None:
    """标准 tar.zst，与 pacman 兼容的压缩格式（注意：不含 PKGINFO，不可 pacman -U）"""
    require_command("zstd", "sudo pacman -S zstd  /  sudo apt install zstd")
    output_file = output_dir / f"{prefix}_linux_{version}_{arch}.tar.zst"
    run_shell_command(
        f"tar --use-compress-program='zstd -19 -T0' -cf {output_file} -C {bundle} ."
    )
    log_success(f"输出: {output_file}")


def package_arch_package(context: BuildContext, arch: str, bundle: Path) -> None:
    """
    生成正规 Arch Linux .pkg.tar.zst
    含 .PKGINFO / .MTREE，可直接 pacman -U 安装。
    原理：生成 PKGBUILD + 预构建 bundle source tarball，
    用 makepkg 打包（不重新编译 Flutter）。
    """
    log_step("打包 Arch Linux .pkg.tar.zst（makepkg）")
    require_command("makepkg", "请在 Arch Linux 系统上运行")

    app_name = resolve_package_name(context.options)
    desktop = get_linux_desktop_file()
    binary_name = resolve_linux_binary_name(bundle, desktop, app_name)
    icon_name = resolve_linux_icon_name(desktop, app_name)
    # pacman 版本号不能含 + -，转成 _
    pkg_ver = re.sub(r"[+\-]", "_", context.version)
    pkg_arch = "x86_64" if arch == "x64" else arch

    work = Path(f"/tmp/{context.prefix}_arch_build")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # ── 把 bundle 打成 source tarball（makepkg 需要 source 文件）──
    src_name = f"{app_name}-{pkg_ver}"
    src_dir = work / src_name
    src_dir.mkdir()
    shutil.copytree(bundle, src_dir / "bundle", dirs_exist_ok=True)

    logo = Path("assets/images/logo/logo.png")
    if desktop:
        shutil.copy2(desktop, src_dir / desktop.name)
    if logo.exists():
        shutil.copy2(logo, src_dir / f"{icon_name}.png")

    src_tar = work / f"{src_name}.tar.gz"
    run_shell_command(f"tar -zcf {src_tar} -C {work} {src_name}")
    sha256 = run_shell_command(
        f"sha256sum {src_tar}", capture_output=True
    ).stdout.split()[0]

    desktop_name = desktop.name if desktop else f"com.example.{app_name}.desktop"

    # ── 写 PKGBUILD ──
    (work / "PKGBUILD").write_text(
        textwrap.dedent(f"""\
        # Maintainer: auto-generated by build.py
        pkgname={app_name}
        pkgver={pkg_ver}
        pkgrel=1
        pkgdesc="Flutter App"
        arch=('{pkg_arch}')
        url="https://github.com"
        license=('GPL-3.0-or-later')
        depends=('gtk3' 'libayatana-appindicator' 'mpv')
        source=("{src_name}.tar.gz")
        sha256sums=('{sha256}')

        package() {{
            cd "$srcdir/{src_name}"

            # 主体文件
            install -dm755 "$pkgdir/opt/{app_name}"
            cp -rdp --no-preserve=ownership bundle/. "$pkgdir/opt/{app_name}/"
            chmod 755 "$pkgdir/opt/{app_name}/{binary_name}"

            # 启动脚本（处理 LD_LIBRARY_PATH，Arch 需要）
            install -dm755 "$pkgdir/usr/bin"
            cat > "$pkgdir/usr/bin/{app_name}" << 'LAUNCHER'
        #!/bin/bash
        LD_LIBRARY_PATH="/opt/{app_name}/lib:$LD_LIBRARY_PATH" exec "/opt/{app_name}/{binary_name}" "$@"
        LAUNCHER
            chmod 755 "$pkgdir/usr/bin/{app_name}"

            # 桌面文件
            install -dm755 "$pkgdir/usr/share/applications"
            [[ -f {desktop_name} ]] && install -Dm644 {desktop_name} \\
                "$pkgdir/usr/share/applications/{desktop_name}"

            # 图标
            install -dm755 "$pkgdir/usr/share/icons/hicolor/512x512/apps"
            [[ -f {icon_name}.png ]] && install -Dm644 {icon_name}.png \
                "$pkgdir/usr/share/icons/hicolor/512x512/apps/{icon_name}.png"
        }}
    """),
        encoding="utf-8",
    )

    # ── 运行 makepkg ──
    run_shell_command(
        "makepkg -f --noconfirm",
        cwd=work,
        env={
            **os.environ,
            "PKGDEST": str(context.output_dir.resolve()),
            "PACKAGER": "build.py <local>",
            "SRCDEST": str(work),
        },
    )

    shutil.rmtree(work, ignore_errors=True)
    for package_file in context.output_dir.glob(f"{app_name}-{pkg_ver}*.pkg.tar.zst"):
        log_success(f"输出: {package_file}")


def map_deb_architecture(arch: str) -> str:
    return {
        "x64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "armv7": "armhf",
        "armhf": "armhf",
    }.get(arch, arch)


def package_deb(context: BuildContext, arch: str, bundle: Path) -> None:
    log_step("打包 deb")
    require_command("dpkg-deb")
    app_name = resolve_package_name(context.options)
    desktop = get_linux_desktop_file()
    icon_name = resolve_linux_icon_name(desktop, app_name)
    deb_arch = map_deb_architecture(arch)
    root = Path(f"/tmp/{context.prefix}_deb")
    if root.exists():
        shutil.rmtree(root)

    for d in [
        "opt/app",
        "usr/share/applications",
        "usr/share/icons/hicolor/512x512/apps",
    ]:
        (root / d).mkdir(parents=True)

    shutil.copytree(bundle, root / "opt/app", dirs_exist_ok=True)

    ctrl_src = Path("assets/linux/DEBIAN")
    (root / "DEBIAN").mkdir(exist_ok=True)
    if ctrl_src.exists():
        shutil.copytree(ctrl_src, root / "DEBIAN", dirs_exist_ok=True)
        ctrl = root / "DEBIAN/control"
        if ctrl.exists():
            txt = ctrl.read_text()
            txt = txt.replace("version_need_change", context.version)
            txt = re.sub(r"^Architecture:\s+\S+", f"Architecture: {deb_arch}", txt, flags=re.MULTILINE)
            size_kb = (
                sum(
                    f.stat().st_size
                    for f in (root / "opt/app").rglob("*")
                    if f.is_file()
                )
                // 1024
                + 1
            )
            txt = txt.replace("size_need_change", str(size_kb))
            ctrl.write_text(txt, encoding="utf-8")
        for s in ["postinst", "postrm", "prerm"]:
            sp = root / "DEBIAN" / s
            if sp.exists():
                sp.chmod(0o755)
    else:
        (root / "DEBIAN/control").write_text(
            f"Package: {app_name}\nVersion: {context.version}\nArchitecture: {deb_arch}\n"
            f"Maintainer: Unknown\nInstalled-Size: 0\nDescription: Flutter App\n"
        )

    if desktop:
        shutil.copy2(desktop, root / "usr/share/applications" / desktop.name)
    logo = Path("assets/images/logo/logo.png")
    if logo.exists():
        shutil.copy2(
            logo, root / f"usr/share/icons/hicolor/512x512/apps/{icon_name}.png"
        )

    output_file = context.platform_output_path("linux", arch, suffix=".deb")
    run_shell_command(
        f"dpkg-deb --build --verbose --root-owner-group {root} {output_file}"
    )
    shutil.rmtree(root, ignore_errors=True)
    log_success(f"输出: {output_file}")


def package_rpm(context: BuildContext, arch: str, bundle: Path) -> None:
    log_step("打包 rpm")
    require_command(
        "rpmbuild", "sudo apt install rpm-build  /  sudo dnf install rpm-build"
    )
    import datetime

    app_name = resolve_package_name(context.options)
    desktop = get_linux_desktop_file()
    binary_name = resolve_linux_binary_name(bundle, desktop, app_name)
    icon_name = resolve_linux_icon_name(desktop, app_name)
    rpm_ver = re.sub(r"[+\-]", "_", context.version)
    rpm_root = Path(f"/tmp/{context.prefix}_rpm")
    for d in ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]:
        (rpm_root / d).mkdir(parents=True, exist_ok=True)

    src_dir = rpm_root / f"{app_name}-{rpm_ver}"
    src_dir.mkdir()
    (src_dir / "bundle").mkdir()
    (src_dir / "assets").mkdir()
    shutil.copytree(bundle, src_dir / "bundle", dirs_exist_ok=True)

    logo = Path("assets/images/logo/logo.png")
    if desktop:
        shutil.copy2(desktop, src_dir / "assets" / desktop.name)
    if logo.exists():
        shutil.copy2(logo, src_dir / f"assets/{icon_name}.png")

    run_shell_command(
        f"tar -zcf {rpm_root}/SOURCES/{app_name}-{rpm_ver}.tar.gz "
        f"-C {rpm_root} {app_name}-{rpm_ver}"
    )

    desktop_name = desktop.name if desktop else f"com.example.{app_name}.desktop"
    date_str = datetime.datetime.now().strftime("%a %b %d %Y")

    (rpm_root / f"SPECS/{app_name}.spec").write_text(
        textwrap.dedent(f"""\
        Name:           {app_name}
        Version:        {rpm_ver}
        Release:        1%{{?dist}}
        Summary:        Flutter App
        License:        GPL-3.0
        Source0:        {app_name}-{rpm_ver}.tar.gz
        Requires:       desktop-file-utils, hicolor-icon-theme

        %description
        Flutter App

        %prep
        %setup -q -n {app_name}-{rpm_ver}

        %build

        %install
        mkdir -p %{{buildroot}}/opt/{app_name}
        cp -r bundle/* %{{buildroot}}/opt/{app_name}/
        chmod 755 %{{buildroot}}/opt/{app_name}/{binary_name}
        mkdir -p %{{buildroot}}/usr/bin
        ln -sf /opt/{app_name}/{binary_name} %{{buildroot}}/usr/bin/{app_name}
        mkdir -p %{{buildroot}}/usr/share/applications
        install -m 644 assets/{desktop_name} \\
            %{{buildroot}}/usr/share/applications/{desktop_name}
        mkdir -p %{{buildroot}}/usr/share/icons/hicolor/512x512/apps
        install -m 644 assets/{icon_name}.png \
            %{{buildroot}}/usr/share/icons/hicolor/512x512/apps/{icon_name}.png

        %post
        update-desktop-database -q || true
        gtk-update-icon-cache -q -t -f %{{_datadir}}/icons/hicolor || true

        %postun
        update-desktop-database -q || true
        gtk-update-icon-cache -q -t -f %{{_datadir}}/icons/hicolor || true

        %files
        /opt/{app_name}
        /usr/bin/{app_name}
        /usr/share/applications/{desktop_name}
        /usr/share/icons/hicolor/512x512/apps/{icon_name}.png

        %changelog
        * {date_str} - {rpm_ver}-1
        - Build
    """),
        encoding="utf-8",
    )

    run_shell_command(
        f"rpmbuild --define '_topdir {rpm_root}' -bb {rpm_root}/SPECS/{app_name}.spec"
    )

    for rpm_file in (rpm_root / "RPMS").rglob("*.rpm"):
        destination = context.platform_output_path("linux", arch, suffix=".rpm")
        shutil.move(str(rpm_file), destination)
        log_success(f"输出: {destination}")

    shutil.rmtree(rpm_root, ignore_errors=True)


def package_appimage(context: BuildContext, arch: str, bundle: Path) -> None:
    log_step("打包 AppImage")
    app_name = resolve_package_name(context.options)
    desktop = get_linux_desktop_file()
    binary_name = resolve_linux_binary_name(bundle, desktop, app_name)
    icon_name = resolve_linux_icon_name(desktop, app_name)
    tool = Path("appimagetool-x86_64.AppImage")
    if not tool.exists():
        download_file(
            "https://github.com/AppImage/appimagetool/releases/"
            "download/continuous/appimagetool-x86_64.AppImage",
            tool,
        )
        tool.chmod(0o755)

    appdir = Path(f"/tmp/{context.prefix}.AppDir")
    if appdir.exists():
        shutil.rmtree(appdir)
    for d in [
        "usr/bin",
        "usr/lib",
        "usr/share/applications",
        "usr/share/icons/hicolor/512x512/apps",
    ]:
        (appdir / d).mkdir(parents=True)

    shutil.copytree(bundle, appdir / "usr/bin", dirs_exist_ok=True)

    logo = Path("assets/images/logo/logo.png")
    if desktop:
        shutil.copy2(desktop, appdir / desktop.name)
        shutil.copy2(desktop, appdir / "usr/share/applications" / desktop.name)
    if logo.exists():
        shutil.copy2(logo, appdir / f"{icon_name}.png")
        shutil.copy2(
            logo, appdir / f"usr/share/icons/hicolor/512x512/apps/{icon_name}.png"
        )

    (appdir / "AppRun").write_text(
        '#!/bin/bash\nSELF=$(readlink -f "$0")\nHERE=${SELF%/*}\n'
        'export PATH="${HERE}/usr/bin:${PATH}"\n'
        'export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"\n'
        f'exec "${{HERE}}/usr/bin/{binary_name}" "$@"\n'
    )
    (appdir / "AppRun").chmod(0o755)

    output_file = context.platform_output_path("linux", arch, suffix=".AppImage")
    run_shell_command(f"ARCH=x86_64 ./{tool} {appdir} {output_file}")
    shutil.rmtree(appdir, ignore_errors=True)
    log_success(f"输出: {output_file}")


# ══════════════════════════════════════════════════════════════════
#  Linux 入口
# ══════════════════════════════════════════════════════════════════


def build_linux(context: BuildContext) -> None:
    if platform_module.system() != "Linux":
        log_error("Linux 构建只能在 Linux")
        sys.exit(1)
    log_step("构建 Linux")

    options = context.options
    arch = options.arch or "x64"

    run_command(create_flutter_build_command("linux", options))

    bundle = Path(f"build/linux/{arch}/release/bundle")
    if not bundle.exists():
        log_error(f"未找到构建产物: {bundle}")
        sys.exit(1)

    targets = set(options.linux_targets or ("tar.gz",))
    if "all" in targets:
        targets = {"tar.gz", "zst", "arch", "deb", "rpm", "appimage"}

    dispatch = {
        "tar.gz": lambda: package_tar_gz(
            context.prefix,
            context.version,
            arch,
            bundle,
            context.output_dir,
        ),
        "zst": lambda: package_tar_zst(
            context.prefix,
            context.version,
            arch,
            bundle,
            context.output_dir,
        ),
        "arch": lambda: package_arch_package(context, arch, bundle),
        "deb": lambda: package_deb(context, arch, bundle),
        "rpm": lambda: package_rpm(context, arch, bundle),
        "appimage": lambda: package_appimage(context, arch, bundle),
    }

    for target in targets:
        if target not in dispatch:
            log_warning(f"未知打包目标: {target}")
            continue
        try:
            dispatch[target]()
        except Exception as exc:
            log_warning(f"{target} 打包失败: {exc}（已跳过）")


# ══════════════════════════════════════════════════════════════════
#  参数解析
# ══════════════════════════════════════════════════════════════════


def parse_arguments() -> BuildOptions:
    parser = argparse.ArgumentParser(
        description="Flutter 多平台构建脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__ + """
透传参数:
  --                    之后的所有参数直接传给 flutter build，例如:
                          python build.py android -- --obfuscate --split-debug-info=./debug
""",
    )
    parser.add_argument(
        "platform", choices=["android", "ios", "macos", "windows", "linux", "all"]
    )

    rename_group = parser.add_argument_group("包名替换")
    rename_group.add_argument(
        "--pkg-id",
        metavar="ID",
        default="com.pili.super",
        help="新 Bundle ID，如 com.myfork.app",
    )
    rename_group.add_argument(
        "--original-pkg-id",
        metavar="ID",
        default="com.example.piliplus",
        help="上游 applicationId（默认: com.example.piliplus）",
    )
    rename_group.add_argument(
        "--app-name",
        metavar="NAME",
        default="PiliSuper",
        help="新 pubspec name / 显示名",
    )
    rename_group.add_argument(
        "--original-app-name",
        metavar="NAME",
        default="PiliPlus",
        help="上游 pubspec name（默认: piliPlus）",
    )
    rename_group.add_argument("--skip-rename", action="store_true")
    rename_group.add_argument(
        "--repo",
        metavar="USER/REPO",
        default="FRBLanApps/PiliSuper",
        help="新仓库路径（默认: FRBLanApps/PiliSuper）",
    )
    rename_group.add_argument(
        "--original-repo",
        metavar="USER/REPO",
        default="bggRGjQaUbCoE/PiliPlus",
        help="上游仓库路径（默认: bggRGjQaUbCoE/PiliPlus）",
    )

    build_group = parser.add_argument_group("构建参数")
    build_group.add_argument(
        "--dart-define-from-file", default="pili_release.json", metavar="FILE"
    )
    build_group.add_argument("--dart-define", action="append", default=[], metavar="K=V")
    build_group.add_argument("--arch", default=None)
    build_group.add_argument("--version", default=None, help="手动版本号，跳过 prebuild 计算")
    build_group.add_argument("--no-prebuild", action="store_true")

    android_group = parser.add_argument_group("Android")
    android_group.add_argument("--no-split", action="store_true")

    android_signing_group = parser.add_argument_group("Android 签名")
    android_signing_group.add_argument("--sign", action="store_true")
    android_signing_group.add_argument("--keystore-file", metavar="PATH")
    android_signing_group.add_argument("--keystore-base64", metavar="B64")
    android_signing_group.add_argument("--key-alias", metavar="ALIAS")
    android_signing_group.add_argument("--key-password", metavar="PASS")
    android_signing_group.add_argument("--store-password", metavar="PASS")
    android_signing_group.add_argument(
        "--clean-keys",
        action="store_true",
        help="构建后删除 key.jks / key.properties（CI 用）",
    )

    windows_group = parser.add_argument_group("Windows")
    windows_group.add_argument("--installer", action="store_true")

    linux_group = parser.add_argument_group("Linux")
    linux_group.add_argument(
        "--linux-targets",
        nargs="+",
        default=["tar.gz"],
        choices=["tar.gz", "zst", "arch", "deb", "rpm", "appimage", "all"],
        help="打包格式。arch = 正规 .pkg.tar.zst（需要 makepkg）；"
        "zst = 仅压缩的 tar.zst（不可 pacman -U）",
    )

    common_group = parser.add_argument_group("通用")
    common_group.add_argument("--output", "-o", default="dist", metavar="DIR")
    common_group.add_argument("--output-prefix", default="PiliSuper", metavar="PREFIX")
    common_group.add_argument(
        "--no-patches", dest="apply_patches", action="store_false", default=True
    )
    common_group.add_argument("--no-pub-get", action="store_true")

    namespace, unknown = parser.parse_known_args()

    # 透传给 flutter build 的参数：只收集 -- 之后的内容，其余 unknown 报警
    try:
        sep = sys.argv.index("--")
        extra_build_args = sys.argv[sep + 1 :]
    except ValueError:
        extra_build_args = []
        if unknown:
            log_warning(f"未知参数（已忽略）: {unknown}")

    return BuildOptions.from_namespace(namespace, extra_build_args)


# ══════════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════════


def main() -> None:
    if not Path("pubspec.yaml").exists():
        log_error("请在 Flutter 项目根目录运行（找不到 pubspec.yaml）")
        sys.exit(1)

    options = parse_arguments()

    # 1. 包名替换（sed + rename CLI）
    apply_project_rename(options)

    # 2. Prebuild（版本号 + pili_release.json）
    version_info = resolve_version_info(options)

    log_info(f"版本: {version_info.version_full}")

    # 3. pub get + patches
    require_command("flutter", "请先安装 Flutter，或把 flutter 加入 PATH")
    run_common_setup(options)

    context = BuildContext.create(options, version_info)

    # 4. 构建
    builders: dict[str, PlatformBuilder] = {
        "android": build_android,
        "ios": build_ios,
        "macos": build_macos,
        "windows": build_windows,
        "linux": build_linux,
    }

    for platform_name in options.target_platforms:
        try:
            builders[platform_name](context)
        except subprocess.CalledProcessError as exc:
            log_error(f"{platform_name} 构建失败: {exc}")
            if options.platform != "all":
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as exc:
            log_error(f"{platform_name} 异常: {exc}")
            raise

    log_success(f"完成！输出: {options.output}/")


if __name__ == "__main__":
    main()
