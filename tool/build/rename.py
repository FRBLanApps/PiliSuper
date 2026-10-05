#!/usr/bin/env python3
"""Rewrite the project identity from the upstream names to the fork names.

The working tree deliberately keeps the upstream identifiers so that merges
from upstream stay conflict-free. This script is the build step that swaps
them for the fork identity across every platform, in six passes:

    dart package   package:PiliPlus/...     ->  package:PiliSuper/...
    display name   "PiliPlus" labels        ->  "PiliSuper"
    binary name    piliplus executables     ->  pilisuper
    bundle id      com.example.piliplus     ->  org.frblanapps.pilisuper
    repository     bggRGjQaUbCoE/PiliPlus   ->  FRBLanApps/PiliSuper
    publisher      com.example copyright    ->  FRBLanApps

Upstream attribution survives on purpose: license headers, credit lines and
git dependency URLs keep naming PiliPlus and bggRGjQaUbCoE.

--pkg-id serves every platform at once: the Android namespace and the
Java/Kotlin source package, the Apple bundle identifier, and the Linux
application id. Only the intersection of their rules is accepted, so a value
that passes here cannot fail later in a platform build:

    two or more segments   Android rejects a dotted-component-less id
    letters and digits     Apple rejects `_`, Java/Kotlin rejects `-`
    leading letter         Android rejects a segment starting with a digit
    no reserved word       `super` as a namespace breaks the Android build

--app-name lands in the pubspec `name:` field, so it must be a Dart identifier
that is not a Dart reserved word; `dart pub get` refuses the project outright
otherwise. Dart's list barely overlaps the Java/Kotlin one, hence the separate
table.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from build_common import (log_error, log_info, log_step, log_success,
                          require_project_root)

SELF_PATH = Path(__file__).resolve()

# Never walked: VCS metadata, tool caches and build output.
SKIP_DIRECTORIES = {".git", ".codegraph", ".dart_tool", ".omo", ".pytest_cache",
                    ".fvm", ".idea", "build", "dist", "node_modules", "Pods",
                    "ephemeral"}

# Hand-maintained, because it mixes fork links with upstream credits.
MANUAL_FILES = {"README.md"}

# A line that credits upstream keeps pointing at the upstream repository.
ATTRIBUTION_LINE = re.compile(r"致敬|原作者|上上游|上游|[Uu]pstream|[Aa]cknowledg|\b[Cc]redit\b")

# Java/Kotlin keywords; a package segment may not be one of them.
RESERVED_WORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "fun", "goto", "if",
    "implements", "import", "in", "infix", "init", "inline", "instanceof",
    "int", "interface", "is", "long", "native", "new", "object", "open",
    "operator", "out", "override", "package", "private", "protected", "public",
    "return", "sealed", "short", "static", "strictfp", "super", "switch",
    "synchronized", "this", "throw", "throws", "transient", "try", "typealias",
    "val", "var", "vararg", "void", "volatile", "when", "where", "while",
}

# Words `dart pub get` refuses in the pubspec `name:` field, verified against
# the Dart 3.44 SDK. Dart's built-in identifiers (`dynamic`, `factory`, `get`,
# `static`, `typedef`, ...) are absent because pub accepts them.
DART_RESERVED_WORDS = {
    "abstract", "as", "assert", "await", "break", "case", "catch", "class",
    "const", "continue", "covariant", "default", "deferred", "do", "else",
    "enum", "export", "extends", "external", "final", "finally", "for", "hide",
    "if", "implements", "import", "in", "interface", "is", "late", "library",
    "mixin", "new", "on", "operator", "part", "required", "rethrow", "return",
    "sealed", "set", "super", "switch", "this", "throw", "try", "type", "var",
    "void", "while", "with", "yield",
}

# Runner fields that hold a user-visible label which `flutter create` seeded
# from the lowercase project name instead of the display name. Pass 2 matches
# the display name case-sensitively and so walks past `piliplus`, after which
# pass 3 would demote these labels to the executable name.
DISPLAY_NAME_FIELDS = (
    re.compile(r'VALUE\s+"(?:FileDescription|ProductName)"'),
    re.compile(r'::FindWindow\(|window\.Create\(L"'),
    re.compile(r"gtk_(?:window|header_bar)_set_title\("),
)

# Runner fields that name the vendor rather than the app; upstream leaves the
# `flutter create` sample value there.
PUBLISHER_FIELDS = (
    re.compile(r'VALUE\s+"(?:CompanyName|LegalCopyright)"'),
    re.compile(r"^\s*PRODUCT_COPYRIGHT\s*="),
)

# Platform runners carry both kinds of field.
RUNNER_TREES = {"windows", "linux", "macos"}


# ---------------------------------------------------------------------------
# 基础工具：校验、遍历、读写、逐文件改写
# ---------------------------------------------------------------------------

def require_valid_pkg_id(pkg_id):
    def reject(reason):
        log_error(f"{pkg_id} 不是合法的跨平台包名：{reason}，将导致构建失败。")
        raise SystemExit(1)

    segments = pkg_id.split(".")
    if len(segments) < 2:
        reject("至少需要两段，Android applicationId 必须包含点分段")
    for segment in segments:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", segment):
            reject(f"段 {segment!r} 必须以字母开头且只含字母与数字"
                   "（Apple bundle id 不接受下划线，Java/Kotlin 包名不接受连字符）")
        if segment in RESERVED_WORDS:
            reject(f"段 {segment!r} 是 Java/Kotlin 保留字，不能用作 Android namespace")


def require_valid_app_name(app_name):
    def reject(reason):
        log_error(f"{app_name} 不是合法的 Dart 包名：{reason}，dart pub get 将拒绝该项目。")
        raise SystemExit(1)

    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", app_name):
        reject("必须是合法的 Dart 标识符（首字符为字母、下划线或 $，其余为字母、数字、"
               "下划线或 $），不能含空格、连字符或点")
    if app_name in DART_RESERVED_WORDS:
        reject("是 Dart 保留字")


def project_files():
    """Every file in the tree, skipping caches, build output and this script."""
    found = []
    for directory, subdirectories, names in os.walk("."):
        subdirectories[:] = sorted(n for n in subdirectories if n not in SKIP_DIRECTORIES)
        for name in names:
            path = Path(directory) / name
            if path.resolve() != SELF_PATH:
                found.append(path)
    return found


def require_no_symlinks(files):
    """Reject links before any rewrite can follow them outside the tree."""
    for directory, subdirectories, names in os.walk("."):
        for name in (*subdirectories, *names):
            path = Path(directory) / name
            if path.is_symlink():
                log_error(f"拒绝处理符号链接: {path}")
                raise SystemExit(1)

    for path in files:
        if path.is_symlink():
            log_error(f"拒绝处理符号链接: {path}")
            raise SystemExit(1)

    pubspec = Path("pubspec.yaml")
    if pubspec.is_symlink():
        log_error(f"拒绝处理符号链接: {pubspec}")
        raise SystemExit(1)


def read_text(path):
    """Contents with line endings kept verbatim, or None if the file is not text."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read()
    except (UnicodeDecodeError, OSError):
        return None


def write_text(path, content):
    if path.is_symlink():
        log_error(f"拒绝写入符号链接: {path}")
        raise SystemExit(1)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def rewrite(files, rewriter):
    """Apply `rewriter` to every readable file, saving only actual changes."""
    for path in files:
        before = read_text(path)
        if before is None:
            continue
        after = rewriter(before)
        if after != before:
            write_text(path, after)
            log_info(f"updated: {path}")


def on_field_lines(fields, substitute):
    """A rewriter that runs `substitute` only on lines holding one of `fields`.

    Keeps the edit off neighbouring lines, so `InternalName` and
    `OriginalFilename` keep the executable name while the label fields beside
    them take the display name.
    """
    def rewriter(text):
        lines = []
        for line in text.splitlines(keepends=True):
            if any(field.search(line) for field in fields):
                line = substitute(line)
            lines.append(line)
        return "".join(lines)

    return rewriter


def spans_to_keep(text, *phrases):
    """Where the old bundle id and the upstream repo path sit in `text`.

    `PiliPlus` also hides inside `com.example.PiliPlus` and
    `bggRGjQaUbCoE/PiliPlus`, so replacing the display name or the binary name
    blindly would corrupt the bundle id and the upstream link. These spans get
    located first; any match overlapping one is left alone.
    """
    wanted = [re.escape(phrase) for phrase in phrases if phrase]
    if not wanted:
        return []
    return [m.span() for m in re.finditer("|".join(wanted), text, re.IGNORECASE)]


def overlaps(span, spans_kept):
    start, end = span
    return any(start < stop and begin < end for begin, stop in spans_kept)


# ---------------------------------------------------------------------------
# Pass 1 —— Dart 包名：每个 import 加 pubspec 自己的 name 字段
# ---------------------------------------------------------------------------

def rename_dart_package(old_app_name, new_app_name, files):
    old_import = f"package:{old_app_name}/"
    new_import = f"package:{new_app_name}/"
    rewrite(files, lambda text: text.replace(old_import, new_import))

    pubspec = Path("pubspec.yaml")
    declared = read_text(pubspec)
    if declared is None:
        return
    renamed = re.sub(
        rf"^(name:\s*){re.escape(old_app_name)}\b",
        rf"\g<1>{new_app_name}",
        declared,
        count=1,
        flags=re.MULTILINE,
    )
    if renamed != declared:
        write_text(pubspec, renamed)
        log_info("updated: pubspec.yaml")


# ---------------------------------------------------------------------------
# Pass 2 —— 显示名：平台标签文件按词替换，Dart 只碰字符串字面量
# ---------------------------------------------------------------------------

def declares_display_label(path):
    """Files whose plain text carries the user-visible app name."""
    parts = path.parts
    top = parts[0]
    name = path.name
    if name == "AndroidManifest.xml" and "android" in parts:
        return True
    if name == "string.xml" and "res" in parts and any(p.startswith("values") for p in parts):
        return True
    if top == "android" and "gradle" in name:
        return True
    if top in {"ios", "macos"} and name.endswith(".plist"):
        return True
    if name == "AppInfo.xcconfig":
        return True
    if name == "make_config.yaml" and parts[:3] == ("windows", "packaging", "exe"):
        return True
    if parts[:2] == ("assets", "linux"):
        return True
    return top == ".vscode" and name.endswith(".json")


def rename_display_name(old_app_name, new_app_name, old_pkg_id, old_repo, files):
    """Platform label files get the name replaced wherever it stands as a word;
    Dart sources only inside string literals, so comments and license headers
    keep saying PiliPlus."""
    old_pkg_path = old_pkg_id.replace(".", "/")
    word = re.compile(rf"\b{re.escape(old_app_name)}\b")
    quoted = re.compile(rf"(['\"]){re.escape(old_app_name)}\1")
    any_case = re.compile(rf"\b{re.escape(old_app_name)}\b", re.IGNORECASE)

    def replace_words(text):
        kept = spans_to_keep(text, old_pkg_id, old_pkg_path, old_repo)
        return word.sub(lambda m: m[0] if overlaps(m.span(), kept) else new_app_name, text)

    def replace_string_literals(text):
        kept = spans_to_keep(text, old_pkg_id, old_pkg_path, old_repo)
        return quoted.sub(
            lambda m: m[0] if overlaps(m.span(), kept) else f"{m[1]}{new_app_name}{m[1]}",
            text,
        )

    def replace_any_case(line):
        kept = spans_to_keep(line, old_pkg_id, old_pkg_path, old_repo)
        return any_case.sub(
            lambda m: m[0] if overlaps(m.span(), kept) else new_app_name, line
        )

    rewrite([p for p in files if declares_display_label(p)], replace_words)
    rewrite([p for p in files if p.parts[0] in {"lib", "test"}], replace_string_literals)
    rewrite(
        [p for p in files if p.parts[0] in RUNNER_TREES],
        on_field_lines(DISPLAY_NAME_FIELDS, replace_any_case),
    )


# ---------------------------------------------------------------------------
# Pass 3 —— 二进制名：CMake target、窗口标题、启动脚本、导出文件名前缀
# ---------------------------------------------------------------------------

def binary_name(app_name):
    """Executable / desktop-entry spelling: PiliSuper -> pilisuper.

    Mirrors the normalization in packaging.py, so the .deb launcher and the
    Linux bundle agree on one name.
    """
    return re.sub(r"[^a-z0-9.+-]", "-", app_name.lower())


def rename_binary_name(old_app_name, new_app_name, old_pkg_id, old_repo, files):
    old_binary = binary_name(old_app_name)
    new_binary = binary_name(new_app_name)
    if old_binary == new_binary:
        return

    old_pkg_path = old_pkg_id.replace(".", "/")
    word = re.compile(rf"\b{re.escape(old_binary)}\b")
    literal_prefix = re.compile(rf"(['\"]){re.escape(old_binary)}")

    def replace_words(text):
        kept = spans_to_keep(text, old_pkg_id, old_pkg_path, old_repo)
        return word.sub(lambda m: m[0] if overlaps(m.span(), kept) else new_binary, text)

    rewrite(
        [p for p in files if p.parts[0] in {"linux", "windows", "macos", "assets"}],
        replace_words,
    )
    rewrite(
        [p for p in files if p.parts[0] in {"lib", "test"}],
        lambda text: literal_prefix.sub(rf"\g<1>{new_binary}", text),
    )


# ---------------------------------------------------------------------------
# Pass 4 —— Bundle id：点分形式（gradle/plist/CMake）与斜杠形式（JNI 类路径）
# ---------------------------------------------------------------------------

def rename_bundle_id(old_pkg_id, new_pkg_id, files):
    old_pkg_path = old_pkg_id.replace(".", "/")
    new_pkg_path = new_pkg_id.replace(".", "/")
    either_spelling = re.compile(
        f"{re.escape(old_pkg_id)}|{re.escape(old_pkg_path)}", re.IGNORECASE
    )

    rewrite(
        files,
        lambda text: either_spelling.sub(
            lambda m: new_pkg_path if "/" in m[0] else new_pkg_id, text
        ),
    )


# ---------------------------------------------------------------------------
# Pass 5 —— 仓库引用：逐行判断，致敬上游的那一行保留上游链接
# ---------------------------------------------------------------------------

def rename_repository(old_repo, new_repo, files):
    def relink(text):
        if old_repo not in text:
            return text
        lines = []
        for line in text.splitlines(keepends=True):
            if not ATTRIBUTION_LINE.search(line):
                line = line.replace(old_repo, new_repo)
            lines.append(line)
        return "".join(lines)

    rewrite([p for p in files if p.name not in MANUAL_FILES], relink)


# ---------------------------------------------------------------------------
# Pass 6 —— 发行者：runner 里 flutter create 留下的 com.example 署名
# ---------------------------------------------------------------------------

def rename_publisher(old_publisher, new_publisher, files):
    """`CompanyName`, `LegalCopyright` and `PRODUCT_COPYRIGHT` still credit the
    `flutter create` sample vendor. Pass 4 walks past them because they carry
    the vendor prefix alone, not the whole bundle id."""
    vendor = re.compile(rf"{re.escape(old_publisher)}(?!\.\w)")

    rewrite(
        [p for p in files if p.parts[0] in RUNNER_TREES],
        on_field_lines(PUBLISHER_FIELDS, lambda line: vendor.sub(new_publisher, line)),
    )


# ---------------------------------------------------------------------------
# 结构性变更：移动源码目录、重命名以 bundle id 命名的文件
# ---------------------------------------------------------------------------

def remove_empty_parents(leaf):
    """Delete the leftover `.../com/example` chain once the package moved out."""
    directory = leaf
    while directory != Path(".") and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def source_directory_operations(old_pkg_id, new_pkg_id):
    """Relocate `.../com/example/piliplus/` source folders to the new package."""
    old_pkg_path = old_pkg_id.replace(".", "/")
    new_pkg_path = new_pkg_id.replace(".", "/")

    sources = []
    for directory, subdirectories, _names in os.walk("."):
        subdirectories[:] = sorted(n for n in subdirectories if n not in SKIP_DIRECTORIES)
        location = Path(directory).as_posix()
        if location == old_pkg_path or location.endswith(f"/{old_pkg_path}"):
            sources.append(Path(directory))
            subdirectories[:] = []  # the package folder is the leaf we move

    return [
        (
            source,
            Path(source.as_posix()[: source.as_posix().rfind(old_pkg_path)] + new_pkg_path),
        )
        for source in sources
    ]


def identity_file_operations(old_pkg_id, new_pkg_id, files=None):
    old_id = re.compile(re.escape(old_pkg_id), re.IGNORECASE)
    operations = []
    for path in files if files is not None else project_files():
        if old_id.search(path.name):
            operations.append((path, path.with_name(old_id.sub(new_pkg_id, path.name))))
    return operations


def require_structural_destinations_available(operations):
    destinations = set()
    for source, target in operations:
        resolved_target = target.absolute()
        if resolved_target in destinations:
            log_error(f"结构目标重复: {source} -> {target}")
            raise SystemExit(1)
        destinations.add(resolved_target)
        if os.path.lexists(target):
            log_error(f"结构目标已存在: {source} -> {target}")
            raise SystemExit(1)


def move_source_directories(old_pkg_id, new_pkg_id, operations=None):
    operations = (
        source_directory_operations(old_pkg_id, new_pkg_id)
        if operations is None
        else operations
    )
    for source, target in operations:
        if os.path.lexists(target):
            log_error(f"结构目标已存在: {source} -> {target}")
            raise SystemExit(1)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        remove_empty_parents(source.parent)
        log_info(f"moved: {source} -> {target}")


def rename_identity_files(old_pkg_id, new_pkg_id, operations=None):
    """Files named after the bundle id, such as `com.example.piliplus.desktop`."""
    operations = (
        identity_file_operations(old_pkg_id, new_pkg_id)
        if operations is None
        else operations
    )
    for path, target in operations:
        if os.path.lexists(target):
            log_error(f"结构目标已存在: {path} -> {target}")
            raise SystemExit(1)
        path.rename(target)
        log_info(f"renamed: {path} -> {target}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pkg-id", default="org.frblanapps.pilisuper")
    parser.add_argument("--original-pkg-id", default="com.example.piliplus")
    parser.add_argument("--app-name", default="PiliSuper")
    parser.add_argument("--original-app-name", default="PiliPlus")
    parser.add_argument("--repo", default="FRBLanApps/PiliSuper")
    parser.add_argument("--original-repo", default="bggRGjQaUbCoE/PiliPlus")
    parser.add_argument("--publisher", default="FRBLanApps")
    parser.add_argument("--original-publisher", default="com.example")
    args = parser.parse_args()

    old_app_name, new_app_name = args.original_app_name, args.app_name
    old_pkg_id, new_pkg_id = args.original_pkg_id, args.pkg_id
    old_repo, new_repo = args.original_repo, args.repo
    old_publisher, new_publisher = args.original_publisher, args.publisher

    require_project_root()
    require_valid_pkg_id(new_pkg_id)
    require_valid_app_name(new_app_name)

    # Listed once, before anything moves: the content passes below all work on
    # pre-rename paths, and the structural passes walk the tree again themselves.
    files = project_files()
    require_no_symlinks(files)

    directory_operations = []
    identity_operations = []
    if new_pkg_id != old_pkg_id:
        directory_operations = source_directory_operations(old_pkg_id, new_pkg_id)
        identity_operations = identity_file_operations(old_pkg_id, new_pkg_id, files)
        require_structural_destinations_available(directory_operations + identity_operations)

    if new_app_name != old_app_name:
        log_step("Rename Dart package")
        rename_dart_package(old_app_name, new_app_name, files)
        log_step("Rename display name")
        rename_display_name(old_app_name, new_app_name, old_pkg_id, old_repo, files)
        log_step("Rename binary name")
        rename_binary_name(old_app_name, new_app_name, old_pkg_id, old_repo, files)

    if new_pkg_id != old_pkg_id:
        log_step("Rename bundle identifier")
        rename_bundle_id(old_pkg_id, new_pkg_id, files)

    if new_repo != old_repo:
        log_step("Rename repository references")
        rename_repository(old_repo, new_repo, files)

    if new_publisher != old_publisher:
        log_step("Rename publisher")
        rename_publisher(old_publisher, new_publisher, files)

    if new_pkg_id != old_pkg_id:
        # Structural changes come last, so every pass above saw the old paths.
        move_source_directories(old_pkg_id, new_pkg_id, directory_operations)
        rename_identity_files(old_pkg_id, new_pkg_id, identity_operations)

    log_success("项目标识已更新")


if __name__ == "__main__":
    main()
