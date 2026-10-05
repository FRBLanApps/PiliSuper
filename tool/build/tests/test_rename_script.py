import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BUILD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD_ROOT))

rename = importlib.import_module("rename")

PKG_ID = "org.frblanapps.pilisuper"
CODE_PATH = "org/frblanapps/pilisuper"


def write(relative: str, content: str) -> None:
    path = Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)


def read(relative: str) -> str:
    with Path(relative).open(encoding="utf-8", newline="") as handle:
        return handle.read()


def make_upstream_project() -> None:
    write("pubspec.yaml",
          "name: PiliPlus\n\ndependencies:\n"
          "  audio_service:\n    git:\n"
          "      url: https://github.com/bggRGjQaUbCoE/audio_service.git\n")
    write("lib/main.dart", "import 'package:PiliPlus/common/constants.dart';\n")
    write("lib/common/constants.dart",
          "abstract final class Constants {\n"
          "  static const appName = 'PiliPlus';\n"
          "  static const sourceCodeUrl = 'https://github.com/bggRGjQaUbCoE/PiliPlus';\n"
          "}\n")
    write("lib/gpl_header.dart",
          "/*\n * This file is part of PiliPlus\n */\n"
          "/// created by bggRGjQaUbCoE on 2025/6/27\n"
          "import 'package:PiliPlus/main.dart';\n")
    write("lib/http/api.dart",
          "const releases = 'https://api.github.com/repos/bggRGjQaUbCoE/PiliPlus/releases';\n")
    write("lib/services/audio_handler.dart",
          "androidNotificationChannelId: 'com.example.piliplus.audio',\n")
    write("lib/utils/android/bindings.g.dart",
          "/// from: `com.example.piliplus.AndroidHelper`\n"
          "class AndroidHelper {\n"
          "  static const classPath = r'com/example/piliplus/AndroidHelper';\n"
          "  String get signature => r'Lcom/example/piliplus/AndroidHelper;';\n"
          "}\n")
    write("lib/pages/backup.dart",
          "return 'piliplus_settings_${DeviceUtils.platformName}.json';\n")
    write("lib/pages/export.dart", "prefix: 'piliplus_${localFileName()}_',\n")
    write("test/app_test.dart", "import 'package:PiliPlus/main.dart';\n")
    write("tool/jnigen/jnigen.dart",
          "classes: ['com.example.piliplus.AndroidHelper'],\n")
    write("tool/patches/example.patch",
          "--- a/lib/main.dart\n+++ b/lib/main.dart\n"
          "@@\n-import 'package:PiliPlus/main.dart';\n")
    write("android/app/build.gradle.kts",
          'android {\n'
          '    namespace = "com.example.piliplus"\n'
          '    defaultConfig {\n'
          '        applicationId = "com.example.piliplus"\n'
          '    }\n'
          '    buildTypes {\n'
          '        debug {\n'
          '            applicationIdSuffix = ".dev"\n'
          '        }\n'
          '    }\n'
          '    productFlavors {\n'
          '        create("dev") {\n'
          '            resValue("string", "app_name", "PiliPlus dev")\n'
          '        }\n'
          '    }\n'
          '}\n')
    write("android/app/src/main/AndroidManifest.xml",
          '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n'
          '    package="com.example.piliplus">\n'
          '    <application android:label="@string/app_name">\n'
          '        <activity android:name=".MainActivity">\n'
          '            <intent-filter android:label="PiliPlus">\n'
          '                <action android:name="com.example.piliplus.SHORTCUT" />\n'
          '            </intent-filter>\n'
          '        </activity>\n'
          '    </application>\n'
          '</manifest>\n')
    write("android/app/src/profile/AndroidManifest.xml",
          '<manifest package="com.example.piliplus">\n</manifest>\n')
    write("android/app/src/main/res/values/string.xml",
          '<resources>\n    <string name="app_name">PiliPlus</string>\n</resources>\n')
    write("android/app/src/debug/res/values/string.xml",
          '<resources>\n    <string name="app_name">PiliPlus debug</string>\n</resources>\n')
    write("android/app/src/main/res/xml-v25/shortcuts.xml",
          '<shortcuts>\n    <intent android:action="com.example.piliplus.SHORTCUT" />\n</shortcuts>\n')
    write("android/app/src/main/kotlin/com/example/piliplus/MainActivity.kt",
          "package com.example.piliplus\n")
    write("android/app/src/main/java/com/example/piliplus/AndroidHelper.java",
          "package com.example.piliplus;\n")
    write("ios/Runner/Info.plist",
          "<dict>\n\t<key>CFBundleDisplayName</key>\n\t<string>PiliPlus</string>\n"
          "\t<key>CFBundleName</key>\n\t<string>PiliPlus</string>\n</dict>\n")
    write("ios/Runner.xcodeproj/project.pbxproj",
          "PRODUCT_BUNDLE_IDENTIFIER = com.example.piliplus;\n"
          "PRODUCT_BUNDLE_IDENTIFIER = com.example.piliplus.RunnerTests;\n")
    write("macos/Runner/Configs/AppInfo.xcconfig",
          "PRODUCT_NAME = PiliPlus\n"
          "PRODUCT_BUNDLE_IDENTIFIER = com.example.piliplus\n"
          "PRODUCT_COPYRIGHT = Copyright © 2023 com.example. All rights reserved.\n")
    write("macos/Runner.xcodeproj/project.pbxproj", "path = piliplus.app;\n")
    write("linux/CMakeLists.txt",
          'set(BINARY_NAME "piliplus")\nset(APPLICATION_ID "com.example.piliplus")\n')
    write("linux/runner/my_application.cc",
          'gtk_header_bar_set_title(header_bar, "piliplus");\n'
          'gtk_window_set_titlebar(window, GTK_WIDGET(header_bar));\n'
          'gtk_window_set_title(window, "piliplus");\n'
          'g_settings_new("com.example.piliplus");\n'
          'g_build_filename(g_get_user_data_dir(), "com.example.piliplus", NULL);\n')
    write("windows/CMakeLists.txt",
          'project(piliplus LANGUAGES CXX)\nset(BINARY_NAME "piliplus")\n')
    write("windows/runner/main.cpp",
          '  HWND hwnd = ::FindWindow(L"FLUTTER_RUNNER_WIN32_WINDOW", L"piliplus");\n'
          '  flutter::DartProject project(L"data");\n'
          '  if (!window.Create(L"piliplus", origin, size)) {\n')
    write("windows/runner/Runner.rc",
          '            VALUE "CompanyName", "com.example" "\\0"\n'
          '            VALUE "FileDescription", "piliplus" "\\0"\n'
          '            VALUE "InternalName", "piliplus" "\\0"\n'
          '            VALUE "LegalCopyright", '
          '"Copyright (C) 2023 com.example. All rights reserved." "\\0"\n'
          '            VALUE "OriginalFilename", "piliplus.exe" "\\0"\n'
          '            VALUE "ProductName", "piliplus" "\\0"\n')
    write("windows/packaging/exe/make_config.yaml",
          "display_name: PiliPlus\n"
          "publisher_url: https://github.com/bggRGjQaUbCoE/PiliPlus\n")
    write("assets/linux/com.example.piliplus.desktop",
          "[Desktop Entry]\nName=PiliPlus\nExec=piliplus\nIcon=piliplus\n"
          "StartupWMClass=com.example.piliplus\n")
    write("assets/linux/DEBIAN/prerm",
          'echo "Stopping PiliPlus if running..."\npkill -x piliplus || true\n')
    write("assets/linux/DEBIAN/postrm",
          "rm -rf /home/*/.local/share/com.example.PiliPlus || true\n")
    write(".github/ISSUE_TEMPLATE/bug.yml",
          "- label: 搜索了 [历史 issue](https://github.com/bggRGjQaUbCoE/PiliPlus/issues?q=is%3Aissue)\n"
          "- label: 搜索了 [上游的历史 issue](https://github.com/bggRGjQaUbCoE/PiliPlus/issues?q=is%3Aissue)\n")
    write(".vscode/launch.json",
          '{\n  "configurations": [\n    {\n      "name": "PiliPlus"\n    }\n  ]\n}\n')
    write("README.md",
          "git clone https://github.com/bggRGjQaUbCoE/PiliPlus.git\n\n"
          "在此致敬原作者：[bggRGjQaUbCoE/PiliPlus](https://github.com/bggRGjQaUbCoE/PiliPlus)\n")
    write("build/skipme.txt", "package:PiliPlus/ com.example.piliplus\n")
    write(".dart_tool/skipme.txt", "package:PiliPlus/\n")
    Path("binary.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00piliplus")
    Path("crlf.txt").write_bytes(
        b"id=com.example.piliplus\r\nimport 'package:PiliPlus/x.dart';\r\n"
    )


def run_rename(*argv: str) -> None:
    with patch.object(sys, "argv", ["rename.py", *argv]):
        rename.main()


def tree_snapshot() -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for root, directories, names in os.walk("."):
        directories[:] = sorted(directories)
        for name in names:
            path = Path(root) / name
            snapshot[path.as_posix()] = path.read_bytes()
    return snapshot


class RenameSandbox(unittest.TestCase):
    """Creates an upstream-named miniature Flutter project in a temp dir."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(temp.name)
        make_upstream_project()


class FullRenameTests(RenameSandbox):
    def test_english_credit_links_survive_repository_rename(self):
        # Given
        upstream = "https://github.com/bggRGjQaUbCoE/PiliPlus"
        write("README.en.md", f"Credit to [{upstream}]({upstream}).\n"
              f"Download: [{upstream}]({upstream}/releases)\n")

        # When
        run_rename()

        # Then
        lines = read("README.en.md").splitlines()
        self.assertIn(upstream, lines[0])
        self.assertIn("https://github.com/FRBLanApps/PiliSuper/releases", lines[1])

    def test_covers_all_platforms(self):
        run_rename()

        self.assertIn("name: PiliSuper", read("pubspec.yaml"))
        self.assertIn("package:PiliSuper/", read("lib/main.dart"))
        self.assertIn("package:PiliSuper/", read("test/app_test.dart"))
        self.assertIn("package:PiliSuper/", read("tool/patches/example.patch"))

        gradle = read("android/app/build.gradle.kts")
        self.assertIn(f'namespace = "{PKG_ID}"', gradle)
        self.assertIn(f'applicationId = "{PKG_ID}"', gradle)
        self.assertIn('applicationIdSuffix = ".dev"', gradle)
        self.assertIn('"PiliSuper dev"', gradle)

        manifest = read("android/app/src/main/AndroidManifest.xml")
        self.assertIn(f'package="{PKG_ID}"', manifest)
        self.assertIn('android:label="@string/app_name"', manifest)
        self.assertIn('android:label="PiliSuper"', manifest)
        self.assertIn(f'<action android:name="{PKG_ID}.SHORTCUT" />', manifest)
        self.assertIn(f'package="{PKG_ID}"',
                      read("android/app/src/profile/AndroidManifest.xml"))
        self.assertIn(f'<intent android:action="{PKG_ID}.SHORTCUT" />',
                      read("android/app/src/main/res/xml-v25/shortcuts.xml"))
        self.assertIn('<string name="app_name">PiliSuper</string>',
                      read("android/app/src/main/res/values/string.xml"))
        self.assertIn('<string name="app_name">PiliSuper debug</string>',
                      read("android/app/src/debug/res/values/string.xml"))

        self.assertTrue(Path(
            f"android/app/src/main/kotlin/{CODE_PATH}/MainActivity.kt").is_file())
        java = Path(f"android/app/src/main/java/{CODE_PATH}/AndroidHelper.java")
        self.assertTrue(java.is_file())
        self.assertIn(f"package {PKG_ID};", read(str(java)))
        self.assertIn(f"package {PKG_ID}",
                      read(f"android/app/src/main/kotlin/{CODE_PATH}/MainActivity.kt"))
        self.assertFalse(Path("android/app/src/main/java/com").exists())
        self.assertFalse(Path("android/app/src/main/kotlin/com").exists())

        self.assertIn("<string>PiliSuper</string>", read("ios/Runner/Info.plist"))
        pbxproj = read("ios/Runner.xcodeproj/project.pbxproj")
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {PKG_ID};", pbxproj)
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {PKG_ID}.RunnerTests;", pbxproj)

        xcconfig = read("macos/Runner/Configs/AppInfo.xcconfig")
        self.assertIn("PRODUCT_NAME = PiliSuper", xcconfig)
        self.assertIn(f"PRODUCT_BUNDLE_IDENTIFIER = {PKG_ID}", xcconfig)
        self.assertIn("PRODUCT_COPYRIGHT = Copyright © 2023 FRBLanApps.", xcconfig)
        self.assertIn("path = pilisuper.app;",
                      read("macos/Runner.xcodeproj/project.pbxproj"))

        linux_cmake = read("linux/CMakeLists.txt")
        self.assertIn('set(BINARY_NAME "pilisuper")', linux_cmake)
        self.assertIn(f'set(APPLICATION_ID "{PKG_ID}")', linux_cmake)
        cc = read("linux/runner/my_application.cc")
        self.assertIn('gtk_window_set_title(window, "PiliSuper")', cc)
        self.assertIn('gtk_header_bar_set_title(header_bar, "PiliSuper")', cc)
        self.assertIn("gtk_window_set_titlebar(window, GTK_WIDGET(header_bar))", cc)
        self.assertIn(f'g_settings_new("{PKG_ID}")', cc)
        self.assertIn(f'g_get_user_data_dir(), "{PKG_ID}"', cc)

        windows_cmake = read("windows/CMakeLists.txt")
        self.assertIn("project(pilisuper LANGUAGES CXX)", windows_cmake)
        self.assertIn('set(BINARY_NAME "pilisuper")', windows_cmake)

        main_cpp = read("windows/runner/main.cpp")
        self.assertIn('::FindWindow(L"FLUTTER_RUNNER_WIN32_WINDOW", L"PiliSuper")',
                      main_cpp)
        self.assertIn('window.Create(L"PiliSuper", origin, size)', main_cpp)
        self.assertIn('flutter::DartProject project(L"data")', main_cpp)

        rc = read("windows/runner/Runner.rc")
        self.assertIn('VALUE "FileDescription", "PiliSuper"', rc)
        self.assertIn('VALUE "ProductName", "PiliSuper"', rc)
        self.assertIn('VALUE "InternalName", "pilisuper"', rc)
        self.assertIn('VALUE "OriginalFilename", "pilisuper.exe"', rc)
        self.assertIn('VALUE "CompanyName", "FRBLanApps"', rc)
        self.assertIn('VALUE "LegalCopyright", "Copyright (C) 2023 FRBLanApps.', rc)

        config = read("windows/packaging/exe/make_config.yaml")
        self.assertIn("display_name: PiliSuper", config)
        self.assertIn("https://github.com/FRBLanApps/PiliSuper", config)

        desktop = read(f"assets/linux/{PKG_ID}.desktop")
        self.assertIn("Name=PiliSuper", desktop)
        self.assertIn("Exec=pilisuper", desktop)
        self.assertIn("Icon=pilisuper", desktop)
        self.assertIn(f"StartupWMClass={PKG_ID}", desktop)
        self.assertFalse(Path("assets/linux/com.example.piliplus.desktop").exists())

        prerm = read("assets/linux/DEBIAN/prerm")
        self.assertIn("Stopping PiliSuper", prerm)
        self.assertIn("pkill -x pilisuper", prerm)
        self.assertIn(f"share/{PKG_ID}", read("assets/linux/DEBIAN/postrm"))

        self.assertIn(f"'{PKG_ID}.audio'",
                      read("lib/services/audio_handler.dart"))
        bindings = read("lib/utils/android/bindings.g.dart")
        self.assertIn(f"`{PKG_ID}.AndroidHelper`", bindings)
        self.assertIn(f"r'{CODE_PATH}/AndroidHelper'", bindings)
        self.assertIn(f"r'L{CODE_PATH}/AndroidHelper;'", bindings)
        self.assertIn(f"'{PKG_ID}.AndroidHelper'", read("tool/jnigen/jnigen.dart"))

        constants = read("lib/common/constants.dart")
        self.assertIn("appName = 'PiliSuper'", constants)
        self.assertIn("https://github.com/FRBLanApps/PiliSuper", constants)
        self.assertIn("FRBLanApps/PiliSuper/releases", read("lib/http/api.dart"))
        self.assertIn("'pilisuper_settings_", read("lib/pages/backup.dart"))
        self.assertIn("'pilisuper_${localFileName()}_'", read("lib/pages/export.dart"))
        self.assertIn('"name": "PiliSuper"', read(".vscode/launch.json"))

    def test_preserves_upstream_attribution(self):
        run_rename()

        gpl = read("lib/gpl_header.dart")
        self.assertIn("This file is part of PiliPlus", gpl)
        self.assertIn("created by bggRGjQaUbCoE", gpl)
        self.assertIn("package:PiliSuper/", gpl)

        readme = read("README.md")
        self.assertIn("git clone https://github.com/bggRGjQaUbCoE/PiliPlus.git", readme)
        self.assertIn("致敬原作者：[bggRGjQaUbCoE/PiliPlus]", readme)

        issues = read(".github/ISSUE_TEMPLATE/bug.yml")
        self.assertIn("https://github.com/FRBLanApps/PiliSuper/issues", issues)
        self.assertIn(
            "[上游的历史 issue](https://github.com/bggRGjQaUbCoE/PiliPlus/issues?q=is%3Aissue)",
            issues)

        self.assertIn("bggRGjQaUbCoE/audio_service.git", read("pubspec.yaml"))
        self.assertIn("package:PiliPlus/", read("build/skipme.txt"))
        self.assertIn("package:PiliPlus/", read(".dart_tool/skipme.txt"))
        self.assertEqual(
            Path("binary.png").read_bytes(),
            b"\x89PNG\r\n\x1a\n\xff\xfe\x00piliplus")
        self.assertEqual(
            Path("crlf.txt").read_bytes(),
            b"id=org.frblanapps.pilisuper\r\nimport 'package:PiliSuper/x.dart';\r\n")

    def test_symlinked_file_aborts_before_mutation(self):
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        outside = Path(external.name) / "outside.dart"
        outside.write_text("const value = 'PiliPlus';\n", encoding="utf-8")
        link = Path("lib/external.dart")
        link.symlink_to(outside)

        with self.assertRaises(SystemExit):
            run_rename()

        self.assertEqual(outside.read_text(encoding="utf-8"), "const value = 'PiliPlus';\n")
        self.assertTrue(link.is_symlink())
        self.assertIn("name: PiliPlus", read("pubspec.yaml"))
        self.assertIn("package:PiliPlus/", read("lib/main.dart"))
        self.assertFalse(Path("assets/linux/org.frblanapps.pilisuper.desktop").exists())

    def test_directory_collision_aborts_before_mutation(self):
        target = Path("android/app/src/main/kotlin/org/frblanapps/pilisuper")
        target.mkdir(parents=True)
        (target / "sentinel.txt").write_text("keep", encoding="utf-8")
        original = read("android/app/src/main/kotlin/com/example/piliplus/MainActivity.kt")

        with self.assertRaises(SystemExit):
            run_rename()

        self.assertTrue(Path("android/app/src/main/kotlin/com/example/piliplus/MainActivity.kt").is_file())
        self.assertEqual(read("android/app/src/main/kotlin/com/example/piliplus/MainActivity.kt"), original)
        self.assertEqual((target / "sentinel.txt").read_text(encoding="utf-8"), "keep")
        self.assertIn("name: PiliPlus", read("pubspec.yaml"))

    def test_identity_file_collision_aborts_before_mutation(self):
        target = Path("assets/linux/org.frblanapps.pilisuper.desktop")
        target.write_text("sentinel", encoding="utf-8")

        with self.assertRaises(SystemExit):
            run_rename()

        self.assertTrue(Path("assets/linux/com.example.piliplus.desktop").is_file())
        self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")
        self.assertIn("name: PiliPlus", read("pubspec.yaml"))

    def test_rename_is_idempotent(self):
        run_rename()
        snapshot = tree_snapshot()
        run_rename()
        self.assertEqual(tree_snapshot(), snapshot)


class DisplayNameOnlyTests(RenameSandbox):
    def test_bundle_id_untouched_when_pkg_id_unchanged(self):
        run_rename("--pkg-id", "com.example.piliplus")

        gradle = read("android/app/build.gradle.kts")
        self.assertIn('namespace = "com.example.piliplus"', gradle)
        self.assertIn('applicationId = "com.example.piliplus"', gradle)
        self.assertIn(f'package="com.example.piliplus"',
                      read("android/app/src/main/AndroidManifest.xml"))

        # 大小写混合的旧 ID 与二进制名同现一文件时，只有后者被替换。
        linux_cmake = read("linux/CMakeLists.txt")
        self.assertIn('set(APPLICATION_ID "com.example.piliplus")', linux_cmake)
        self.assertIn('set(BINARY_NAME "pilisuper")', linux_cmake)
        self.assertIn("share/com.example.PiliPlus",
                      read("assets/linux/DEBIAN/postrm"))

        self.assertIn('<string name="app_name">PiliSuper</string>',
                      read("android/app/src/main/res/values/string.xml"))
        self.assertIn("appName = 'PiliSuper'", read("lib/common/constants.dart"))
        self.assertTrue(Path(
            "android/app/src/main/java/com/example/piliplus/AndroidHelper.java").is_file())
        self.assertTrue(Path("assets/linux/com.example.piliplus.desktop").is_file())
        self.assertIn("FRBLanApps/PiliSuper/releases", read("lib/http/api.dart"))

        # 发行者与 bundle id 各自独立：署名换掉，包名保持原样。
        rc = read("windows/runner/Runner.rc")
        self.assertIn('VALUE "CompanyName", "FRBLanApps"', rc)
        self.assertIn('VALUE "FileDescription", "PiliSuper"', rc)
        self.assertIn('VALUE "OriginalFilename", "pilisuper.exe"', rc)
        self.assertIn("Copyright © 2023 FRBLanApps.",
                      read("macos/Runner/Configs/AppInfo.xcconfig"))


class PublisherTests(RenameSandbox):
    def test_publisher_untouched_when_unchanged(self):
        run_rename("--publisher", "com.example")

        rc = read("windows/runner/Runner.rc")
        self.assertIn('VALUE "CompanyName", "com.example"', rc)
        self.assertIn("Copyright (C) 2023 com.example.", rc)
        self.assertIn("Copyright © 2023 com.example.",
                      read("macos/Runner/Configs/AppInfo.xcconfig"))


class ValidationTests(RenameSandbox):
    def assertRejected(self, *argv: str) -> None:
        with self.assertRaises(SystemExit):
            run_rename(*argv)
        self.assertIn("name: PiliPlus", read("pubspec.yaml"))

    def assertPkgIdRejected(self, pkg_id: str) -> None:
        self.assertRejected("--pkg-id", pkg_id)

    def assertAppNameRejected(self, app_name: str) -> None:
        self.assertRejected("--app-name", app_name)

    def test_reserved_word_package_rejected(self):
        self.assertPkgIdRejected("com.pili.super")

    def test_invalid_segment_package_rejected(self):
        self.assertPkgIdRejected("org.frblanapps.pili+super")

    def test_single_segment_package_rejected(self):
        self.assertPkgIdRejected("foo")

    def test_underscore_package_rejected(self):
        self.assertPkgIdRejected("org.example.my_app")

    def test_hyphen_package_rejected(self):
        self.assertPkgIdRejected("org.example.my-app")

    def test_leading_digit_segment_rejected(self):
        self.assertPkgIdRejected("org.example.2fast")

    def test_empty_segment_rejected(self):
        self.assertPkgIdRejected("org..example")

    def test_dart_reserved_app_name_rejected(self):
        for app_name in ("mixin", "class", "with", "await", "required", "type"):
            with self.subTest(app_name=app_name):
                self.assertAppNameRejected(app_name)

    def test_non_identifier_app_name_rejected(self):
        for app_name in ("Pili-Super", "Pili Super", "2fast", "Pili.Super",
                         "Pili+Super", ""):
            with self.subTest(app_name=app_name):
                self.assertAppNameRejected(app_name)

    def test_dart_builtin_identifier_app_name_accepted(self):
        """`dart pub get` accepts built-in identifiers, so neither may this."""
        run_rename("--app-name", "dynamic")
        self.assertIn("name: dynamic", read("pubspec.yaml"))


class WorkflowTests(unittest.TestCase):
    def test_user_inputs_are_not_embedded_in_shell_run_blocks(self):
        workflow = BUILD_ROOT.parents[1] / ".github" / "workflows" / "build.yml"
        lines = workflow.read_text(encoding="utf-8").splitlines()
        in_run = False
        run_indent = 0
        shell_lines = []
        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if stripped.startswith("run:"):
                in_run = True
                run_indent = indent
                shell_lines.append(stripped[4:])
                continue
            if in_run and stripped and indent <= run_indent:
                in_run = False
            if in_run:
                shell_lines.append(line)

        self.assertTrue(shell_lines)
        self.assertNotIn("${{ inputs.", "\n".join(shell_lines))


if __name__ == "__main__":
    unittest.main()
