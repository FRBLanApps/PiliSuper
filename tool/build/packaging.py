#!/usr/bin/env python3
"""Package an existing Linux Flutter bundle; it never runs Flutter builds.

The tar.gz and AppImage bundles rely on host runtime libraries, including
WebKitGTK 4.1; they do not bundle the system WebKit runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from build_common import log_success, require_command, run_command

PACKAGE_NAME = "pilisuper"
DESKTOP_FILE_NAME = "org.frblanapps.pilisuper.desktop"
LEGACY_DESKTOP_FILE_NAME = "com.pili.super.desktop"
ICON_NAME = "pilisuper"


@dataclass(frozen=True)
class PackageIdentity:
    package_name: str
    desktop_file_name: str
    icon_name: str


def package_identity(pkg_id: str) -> PackageIdentity:
    if pkg_id == "org.frblanapps.pilisuper":
        return PackageIdentity(PACKAGE_NAME, DESKTOP_FILE_NAME, ICON_NAME)
    if pkg_id == "com.pili.super":
        return PackageIdentity(PACKAGE_NAME, LEGACY_DESKTOP_FILE_NAME, ICON_NAME)
    normalized = re.sub(r"[^a-z0-9.+-]", "-", pkg_id.lower())
    return PackageIdentity(normalized, f"{normalized}.desktop", normalized)


def bundle_path(arch: str, explicit_path: str | None) -> Path:
    path = Path(explicit_path) if explicit_path else Path(f"build/linux/{arch}/release/bundle")
    if not path.is_dir():
        raise SystemExit(f"未找到 Linux bundle: {path}；请先运行 build_linux.py")
    return path


def output_path(output: str, prefix: str, version: str, arch: str, suffix: str) -> Path:
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{prefix}_linux_{version}_{arch}{suffix}"


def find_bundle_binary(bundle: Path) -> str:
    executables = [path.name for path in bundle.iterdir() if path.is_file() and path.stat().st_mode & 0o111]
    if len(executables) != 1:
        raise SystemExit(f"Linux bundle 应包含一个可执行文件，实际找到: {executables}")
    return executables[0]


def create_install_tree(
    bundle: Path, root: Path, app_name: str, identity: PackageIdentity
) -> None:
    binary = find_bundle_binary(bundle)
    app_dir = root / "opt" / identity.package_name
    shutil.copytree(bundle, app_dir)

    launcher = root / "usr" / "bin" / identity.package_name
    launcher.parent.mkdir(parents=True)
    launcher.write_text(
        "#!/bin/sh\n"
        f"APP_DIR=/opt/{identity.package_name}\n"
        'export LD_LIBRARY_PATH="$APP_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        f'exec "$APP_DIR/{binary}" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    desktop_file = root / "usr" / "share" / "applications" / identity.desktop_file_name
    desktop_file.parent.mkdir(parents=True)
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app_name}\n"
        f"Exec={identity.package_name} %U\n"
        f"Icon={identity.icon_name}\n"
        "Categories=AudioVideo;\n"
        "Terminal=false\n"
        "StartupNotify=true\n",
        encoding="utf-8",
    )

    icon = Path("assets/images/logo/logo.png")
    if not icon.is_file():
        raise SystemExit(f"缺少应用图标: {icon}")
    icon_destination = root / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps" / f"{identity.icon_name}.png"
    icon_destination.parent.mkdir(parents=True)
    shutil.copy2(icon, icon_destination)


def package_tar(bundle: Path, destination: Path, zstd: bool) -> None:
    if zstd:
        require_command("zstd")
        run_command(["tar", "--zstd", "-cf", str(destination), "-C", str(bundle), "."])
    else:
        run_command(["tar", "-zcf", str(destination), "-C", str(bundle), "."])
    log_success(f"输出: {destination}")


def package_appimage(
    bundle: Path,
    destination: Path,
    app_name: str,
    arch: str,
    identity: PackageIdentity,
) -> None:
    if arch not in ("x64", "amd64"):
        raise SystemExit("当前仅支持使用 x86_64 AppImage 工具打包 x64 bundle")

    tool = Path("appimagetool-x86_64.AppImage")
    if not tool.is_file():
        url = (
            "https://github.com/AppImage/appimagetool/releases/"
            "download/continuous/appimagetool-x86_64.AppImage"
        )
        with urlopen(url, timeout=60) as response, tool.open("wb") as output:
            shutil.copyfileobj(response, output)
        tool.chmod(0o755)

    binary = find_bundle_binary(bundle)
    with tempfile.TemporaryDirectory(prefix="pilisuper-appimage-") as temp:
        appdir = Path(temp) / f"{identity.package_name}.AppDir"
        appdir.mkdir()
        shutil.copytree(bundle, appdir / "usr" / "bin")

        desktop = appdir / identity.desktop_file_name
        desktop.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={app_name}\n"
            f"Exec={identity.package_name} %U\n"
            f"Icon={identity.icon_name}\n"
            "Categories=AudioVideo;\n"
            "Terminal=false\n",
            encoding="utf-8",
        )

        icon = Path("assets/images/logo/logo.png")
        if not icon.is_file():
            raise SystemExit(f"缺少应用图标: {icon}")
        shutil.copy2(icon, appdir / f"{identity.icon_name}.png")

        app_run = appdir / "AppRun"
        app_run.write_text(
            "#!/bin/sh\n"
            'HERE="$(dirname "$(readlink -f "$0")")"\n'
            'export LD_LIBRARY_PATH="$HERE/usr/bin/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
            f'exec "$HERE/usr/bin/{binary}" "$@"\n',
            encoding="utf-8",
        )
        app_run.chmod(0o755)
        run_command([str(tool.resolve()), "--appimage-extract-and-run", str(appdir), str(destination)], env={**os.environ, "ARCH": "x86_64"})
    log_success(f"输出: {destination}")


def package_deb(
    bundle: Path,
    destination: Path,
    app_name: str,
    arch: str,
    version: str,
    identity: PackageIdentity,
) -> None:
    require_command("dpkg-deb")
    deb_arch = {"x64": "amd64", "arm64": "arm64", "armv7": "armhf"}.get(arch, arch)
    with tempfile.TemporaryDirectory(prefix="pilisuper-deb-") as temp:
        root = Path(temp)
        create_install_tree(bundle, root, app_name, identity)
        control = root / "DEBIAN"
        control.mkdir()
        installed_size = sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) // 1024 + 1
        (control / "control").write_text(
            f"Package: {identity.package_name}\n"
            f"Version: {version}\n"
            f"Architecture: {deb_arch}\n"
            "Maintainer: FRBLanApps Members <frblanapps@disroot.org>\n"
            "Section: video\n"
            "Priority: optional\n"
            f"Installed-Size: {installed_size}\n"
            # Debian/Ubuntu: ayatana 为主；部分衍生版仅有 libappindicator3-1
            # json-glib: ffmpeg_kit_flutter 的原生层链接它来构造返回值
            "Depends: libgtk-3-0, libmpv2, libjson-glib-1.0-0, libwebkit2gtk-4.1-0,"
            " libayatana-appindicator3-1 | libappindicator3-1\n"
            "Homepage: https://github.com/FRBLanApps/PiliSuper\n"
            f"Description: {app_name}, a third-party Bilibili client\n",
            encoding="utf-8",
        )
        run_command(["dpkg-deb", "--build", "--root-owner-group", str(root), str(destination)])
    log_success(f"输出: {destination}")


def package_arch(
    bundle: Path,
    destination: Path,
    app_name: str,
    arch: str,
    version: str,
    identity: PackageIdentity,
) -> None:
    require_command("makepkg", "请在 Arch Linux 环境中安装 base-devel")
    package_arch = {"x64": "x86_64", "arm64": "aarch64", "armv7": "armv7h"}.get(arch, arch)
    package_version = re.sub(r"[\s/:_-]", ".", version)

    with tempfile.TemporaryDirectory(prefix="pilisuper-arch-") as temp:
        work = Path(temp)
        source_name = f"{identity.package_name}-{package_version}"
        source_root = work / source_name
        create_install_tree(bundle, source_root, app_name, identity)

        source_archive = work / f"{source_name}.tar.gz"
        run_command(["tar", "-zcf", str(source_archive), "-C", str(work), source_name])
        checksum = hashlib.sha256(source_archive.read_bytes()).hexdigest()

        pkgbuild = work / "PKGBUILD"
        pkgbuild.write_text(
            f"pkgname={identity.package_name}\n"
            f"pkgver={package_version}\n"
            "pkgrel=1\n"
            f"pkgdesc='{app_name}, a third-party Bilibili client'\n"
            f"arch=('{package_arch}')\n"
            "url='https://github.com/FRBLanApps/PiliSuper'\n"
            "license=('GPL-3.0-or-later')\n"
            "options=('!debug')\n"
            # Arch 官方仓有 libayatana-appindicator
            "depends=('gtk3' 'mpv' 'json-glib' 'webkit2gtk-4.1' 'libayatana-appindicator')\n"
            f"source=('{source_archive.name}')\n"
            f"sha256sums=('{checksum}')\n\n"
            "package() {\n"
            f"  cd \"$srcdir/{source_name}\"\n"
            "  cp -a opt usr \"$pkgdir/\"\n"
            "}\n",
            encoding="utf-8",
        )

        run_command(
            ["makepkg", "--force", "--noconfirm"],
            cwd=work,
            env={
                **os.environ,
                "PKGDEST": str(work),
                "PACKAGER": "FRBLanApps <frblanapps@disroot.org>",
            },
        )
        packages = list(work.glob(f"{identity.package_name}-*.pkg.tar.zst"))
        if len(packages) != 1:
            raise SystemExit(f"makepkg 产物数量异常: {packages}")
        shutil.copy2(packages[0], destination)
    log_success(f"输出: {destination}")


def package_rpm(
    bundle: Path,
    destination: Path,
    app_name: str,
    arch: str,
    version: str,
    identity: PackageIdentity,
) -> None:
    require_command("rpmbuild", "请安装 rpm-build")
    rpm_arch = {"x64": "x86_64", "arm64": "aarch64", "armv7": "armv7hl"}.get(arch, arch)
    rpm_version = re.sub(r"[^A-Za-z0-9._+~]", ".", version)

    with tempfile.TemporaryDirectory(prefix="pilisuper-rpm-") as temp:
        top = Path(temp)
        for name in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
            (top / name).mkdir()

        source_name = f"{identity.package_name}-{rpm_version}"
        source_root = top / source_name
        create_install_tree(bundle, source_root, app_name, identity)
        source_archive = top / "SOURCES" / f"{source_name}.tar.gz"
        run_command(["tar", "-zcf", str(source_archive), "-C", str(top), source_name])
        shutil.rmtree(source_root)

        spec = top / "SPECS" / f"{identity.package_name}.spec"
        spec.write_text(
            f"Name: {identity.package_name}\n"
            f"Version: {rpm_version}\n"
            "Release: 1%{?dist}\n"
            f"Summary: {app_name}, a third-party Bilibili client\n"
            "License: GPL-3.0-or-later\n"
            "URL: https://github.com/FRBLanApps/PiliSuper\n"
            f"Source0: {source_name}.tar.gz\n"
            f"BuildArch: {rpm_arch}\n"
            # RHEL/Alma/Rocky 无 ayatana 包；Fedora/EPEL 提供 libappindicator-gtk3
            # 托盘为桌面可选能力，故用 Recommends（无则仍可装，缺托盘）
            "Requires: gtk3, mpv, json-glib, webkit2gtk4.1\n"
            "Recommends: libappindicator-gtk3\n\n"
            f"%description\n{app_name}, a third-party Bilibili client.\n\n"
            "%prep\n%setup -q\n\n"
            "%install\n"
            "mkdir -p %{buildroot}\n"
            "cp -a opt usr %{buildroot}/\n\n"
            "%files\n"
            f"/opt/{identity.package_name}\n"
            f"/usr/bin/{identity.package_name}\n"
            f"/usr/share/applications/{identity.desktop_file_name}\n"
            f"/usr/share/icons/hicolor/512x512/apps/{identity.icon_name}.png\n",
            encoding="utf-8",
        )
        run_command(["rpmbuild", "--define", f"_topdir {top}", "-bb", str(spec)])
        rpm_files = list((top / "RPMS").rglob("*.rpm"))
        if len(rpm_files) != 1:
            raise SystemExit(f"rpmbuild 产物数量异常: {rpm_files}")
        shutil.copy2(rpm_files[0], destination)
    log_success(f"输出: {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--arch", default="x64")
    parser.add_argument("--bundle", help="使用指定的已构建 Linux bundle")
    parser.add_argument("--output", default="dist")
    parser.add_argument("--output-prefix", default="PiliSuper")
    parser.add_argument("--app-name", default="PiliSuper")
    parser.add_argument("--pkg-id", default="org.frblanapps.pilisuper")
    parser.add_argument("targets", nargs="+", choices=["tar.gz", "zst", "deb", "rpm", "arch", "appimage"])
    args = parser.parse_args()

    bundle = bundle_path(args.arch, args.bundle)
    identity = package_identity(args.pkg_id)
    for target in args.targets:
        if target == "tar.gz":
            package_tar(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".tar.gz"), False)
        elif target == "zst":
            package_tar(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".tar.zst"), True)
        elif target == "deb":
            package_deb(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".deb"), args.app_name, args.arch, args.version, identity)
        elif target == "rpm":
            package_rpm(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".rpm"), args.app_name, args.arch, args.version, identity)
        elif target == "arch":
            package_arch(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".pkg.tar.zst"), args.app_name, args.arch, args.version, identity)
        else:
            package_appimage(bundle, output_path(args.output, args.output_prefix, args.version, args.arch, ".AppImage"), args.app_name, args.arch, identity)


if __name__ == "__main__":
    main()
