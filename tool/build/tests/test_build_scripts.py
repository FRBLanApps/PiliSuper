import importlib
import os
import sys
import tempfile
import unittest
from contextlib import chdir, nullcontext
from pathlib import Path
from unittest.mock import call, patch


BUILD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD_ROOT))

build_common = importlib.import_module("build_common")
build_android = importlib.import_module("build_android")
build_ios = importlib.import_module("build_ios")
build_macos = importlib.import_module("build_macos")
packaging = importlib.import_module("packaging")
notify_telegram = importlib.import_module("notify_telegram")
patch_script = importlib.import_module("patch")
prebuild = importlib.import_module("prebuild")


class BuildCommonTests(unittest.TestCase):
    def test_output_path(self):
        with tempfile.TemporaryDirectory() as temp:
            path = build_common.output_path(
                temp, "PiliSuper", "android", "2.1.0+10", "arm64-v8a", suffix=".apk"
            )
            self.assertEqual(path.name, "PiliSuper_android_2.1.0+10_arm64-v8a.apk")
            self.assertTrue(path.parent.is_dir())

    def test_flutter_build_dry_run_command(self):
        with patch.object(build_common, "require_command"), patch.object(
            build_common, "run_command"
        ) as run:
            build_common.flutter_build(
                "apk", "missing-release.json", ["--split-per-abi"]
            )

        run.assert_called_once_with(
            ["flutter", "build", "apk", "--release", "--no-pub", "--split-per-abi"]
        )


class AndroidBuildTests(unittest.TestCase):
    def test_split_build_requires_all_abis(self):
        with tempfile.TemporaryDirectory() as temp:
            apk_dir = Path(temp)
            for abi in build_android.SPLIT_ABIS[:-1]:
                (apk_dir / f"app-{abi}-release.apk").write_bytes(b"apk")

            with self.assertRaisesRegex(SystemExit, "x86_64"):
                build_android.built_apks(apk_dir, no_split=False)

    def test_universal_build_selects_only_universal_apk(self):
        with tempfile.TemporaryDirectory() as temp:
            apk_dir = Path(temp)
            universal = apk_dir / "app-release.apk"
            universal.write_bytes(b"apk")
            for abi in build_android.SPLIT_ABIS:
                (apk_dir / f"app-{abi}-release.apk").write_bytes(b"stale")

            self.assertEqual(build_android.built_apks(apk_dir, no_split=True), [universal])


class IOSBuildTests(unittest.TestCase):
    def test_zip_uses_argv_when_output_prefix_contains_shell_metacharacters(self):
        # Given
        with tempfile.TemporaryDirectory() as temp:
            output_prefix = "Pili$(touch-owned)"
            destination = Path("dist") / f"{output_prefix}_ios_2.1.0.ipa"
            with chdir(temp), patch.object(
                sys,
                "argv",
                ["build_ios.py", "--version", "2.1.0", "--output-prefix", output_prefix],
            ), patch.object(build_ios.platform, "system", return_value="Darwin"), patch.object(
                build_ios, "require_project_root"
            ), patch.object(build_ios, "flutter_build"), patch.object(
                build_common.subprocess, "run"
            ) as run:
                # When
                build_ios.main()

            # Then
            self.assertEqual(
                run.call_args_list[-1],
                call(
                    ["zip", "-r9", str(destination), "Payload/Runner.app"],
                    text=True,
                    check=True,
                ),
            )


class MacOSBuildTests(unittest.TestCase):
    def test_create_dmg_uses_argv_when_app_name_contains_shell_metacharacters(self):
        # Given
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "build/macos/Build/Products/Release/Pili`touch-owned`.app"
            app.mkdir(parents=True)
            dmg_temp = root / "dmg-temp"
            dmg_temp.mkdir()
            (dmg_temp / "PiliSuper.dmg").write_bytes(b"dmg")
            with chdir(root), patch.object(
                sys, "argv", ["build_macos.py", "--version", "2.1.0"]
            ), patch.object(build_macos.platform, "system", return_value="Darwin"), patch.object(
                build_macos, "require_project_root"
            ), patch.object(build_macos, "flutter_build"), patch.object(
                build_macos.shutil, "which", return_value="/usr/local/bin/create-dmg"
            ), patch.object(
                build_macos.tempfile,
                "TemporaryDirectory",
                return_value=nullcontext(str(dmg_temp)),
            ), patch.object(build_common.subprocess, "run") as run:
                # When
                build_macos.main()

            # Then
            run.assert_called_once_with(
                ["create-dmg", str(app.resolve())],
                text=True,
                check=False,
                cwd=str(dmg_temp),
            )

    def test_zip_uses_argv_when_paths_contain_shell_metacharacters(self):
        # Given
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Path("build/macos/Build/Products/Release/Pili`touch-owned`.app")
            (root / app).mkdir(parents=True)
            output_prefix = "Pili$(touch-owned)"
            destination = Path("dist") / f"{output_prefix}_macos_2.1.0.zip"
            with chdir(root), patch.object(
                sys,
                "argv",
                ["build_macos.py", "--version", "2.1.0", "--output-prefix", output_prefix],
            ), patch.object(build_macos.platform, "system", return_value="Darwin"), patch.object(
                build_macos, "require_project_root"
            ), patch.object(build_macos, "flutter_build"), patch.object(
                build_macos.shutil, "which", return_value=None
            ), patch.object(build_common.subprocess, "run") as run:
                # When
                build_macos.main()

            # Then
            run.assert_called_once_with(
                ["zip", "-r9", str(destination), str(app)],
                text=True,
                check=True,
            )


class PackagingTests(unittest.TestCase):
    def test_find_bundle_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            binary = bundle / "PiliSuper"
            binary.write_bytes(b"binary")
            binary.chmod(0o755)
            (bundle / "lib.so").write_bytes(b"library")
            self.assertEqual(packaging.find_bundle_binary(bundle), "PiliSuper")

    def test_create_install_tree_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            bundle = Path(temp) / "bundle"
            bundle.mkdir()
            binary = bundle / "PiliSuper"
            binary.write_bytes(b"binary")
            binary.chmod(0o755)
            (bundle / "libPiliSuper.so").write_bytes(b"library")

            # The function only prepares files; no external package tool runs.
            packaging.create_install_tree(
                bundle,
                root,
                "PiliSuper",
                packaging.package_identity("com.pili.super"),
            )

            launcher = root / "usr" / "bin" / "pilisuper"
            self.assertTrue(launcher.is_file())
            self.assertIn('exec "$APP_DIR/PiliSuper"', launcher.read_text())

    def test_custom_package_identity_avoids_pilisuper_collision(self):
        identity = packaging.package_identity("org.example.client")
        self.assertEqual(identity.package_name, "org.example.client")
        self.assertEqual(identity.desktop_file_name, "org.example.client.desktop")


class PrebuildTests(unittest.TestCase):
    def test_android_display_version_includes_commit(self):
        self.assertEqual(
            prebuild.display_version_for("android", "2.1.0", "abcdef123456"),
            "2.1.0-abcdef123",
        )

    def test_non_android_display_version_is_unchanged(self):
        self.assertEqual(
            prebuild.display_version_for("linux", "2.1.0", "abcdef123456"),
            "2.1.0",
        )


class PatchTests(unittest.TestCase):
    def test_already_applied_project_patch_is_accepted(self):
        completed = type("Completed", (), {"returncode": 0})()
        with patch.object(patch_script, "run_command", side_effect=[
            type("Completed", (), {"returncode": 1})(),
            completed,
        ]) as run:
            patch_script.apply_project_patch(Path("patch.diff"), Path("."))

        self.assertEqual(run.call_count, 2)


class TelegramNotifyTests(unittest.TestCase):
    def test_find_artifacts_filters_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "a").mkdir()
            (output / "b").mkdir()
            (output / "a" / "PiliSuper.apk").write_bytes(b"same")
            (output / "b" / "PiliSuper.apk").write_bytes(b"same")
            (output / "b" / "notes.txt").write_text("ignored")

            artifacts = notify_telegram.find_artifacts(output)

            self.assertEqual([item.name for item in artifacts], ["PiliSuper.apk"])

    def test_missing_credentials_skip_notification(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            sys, "argv", ["notify_telegram.py"]
        ):
            self.assertEqual(notify_telegram.main(), 0)

    def test_message_escapes_commit_and_artifact_names(self):
        artifact = notify_telegram.Artifact(Path("a.apk"), "a<1>.apk", 1024)
        message = notify_telegram.build_message(
            label="Build <ready>",
            repository="owner/repo",
            branch="main",
            commit_sha="abcdef123456",
            commit_message="fix <tag>",
            run_url="https://example.test/run",
            artifacts=[artifact],
            skipped=[],
            release_tag="",
        )
        self.assertIn("Build &lt;ready&gt;", message)
        self.assertIn("fix &lt;tag&gt;", message)

    def test_release_message_is_labeled(self):
        message = notify_telegram.build_message(
            label="Build",
            repository="owner/repo",
            branch="main",
            commit_sha="abcdef123456",
            commit_message="release",
            run_url="https://example.test/run",
            artifacts=[],
            skipped=[],
            release_tag="v2.1.0",
        )
        self.assertIn("这是一个 Release", message)
        self.assertIn("v2.1.0", message)
        self.assertIn("#Release", message)

    def test_dev_build_has_dev_tag(self):
        message = notify_telegram.build_message(
            label="Build",
            repository="owner/repo",
            branch="main",
            commit_sha="abcdef123456",
            commit_message="dev build",
            run_url="https://example.test/run",
            artifacts=[],
            skipped=[],
            release_tag="",
        )
        self.assertIn("#Dev", message)

    def test_detect_release_type_dev(self):
        self.assertEqual(notify_telegram.detect_release_type(""), "#Dev")

    def test_detect_release_type_alpha(self):
        self.assertEqual(notify_telegram.detect_release_type("v1.0.0-alpha"), "#Alpha")
        self.assertEqual(notify_telegram.detect_release_type("v1.0.0-ALPHA.1"), "#Alpha")

    def test_detect_release_type_beta(self):
        self.assertEqual(notify_telegram.detect_release_type("v1.0.0-beta"), "#Beta")
        self.assertEqual(notify_telegram.detect_release_type("v1.0.0-BETA.2"), "#Beta")

    def test_detect_release_type_stable(self):
        self.assertEqual(notify_telegram.detect_release_type("v2.1.0"), "#Release")

    def test_find_artifacts_only_matches_pilisuper_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "PiliSuper.exe").write_bytes(b"content1")
            (output / "pilisuper_android.apk").write_bytes(b"content2")
            (output / "PILISUPER.dmg").write_bytes(b"content3")
            (output / "piliplus.exe").write_bytes(b"excluded")
            (output / "other.zip").write_bytes(b"excluded")

            artifacts = notify_telegram.find_artifacts(output)

            names = [item.name for item in artifacts]
            self.assertIn("PiliSuper.exe", names)
            self.assertIn("pilisuper_android.apk", names)
            self.assertIn("PILISUPER.dmg", names)
            self.assertEqual(len(names), 3)

    def test_send_media_group_returns_first_message_id(self):
        with tempfile.TemporaryDirectory() as temp:
            file_a = Path(temp) / "a.apk"
            file_a.write_bytes(b"content_a")

            client = notify_telegram.TelegramClient("fake_token", "fake_chat", None)
            artifacts = [notify_telegram.Artifact(file_a, "PiliSuper.apk", 1024)]

            with patch("urllib.request.urlopen") as urlopen_mock:
                urlopen_mock.return_value.__enter__.return_value.read.return_value = (
                    b'{"ok": true, "result": [{"message_id": 123}, {"message_id": 124}]}'
                )
                message_id = client.send_media_group(artifacts, caption="Test caption")

            self.assertEqual(message_id, 123)
            call_args = urlopen_mock.call_args
            self.assertIn("sendMediaGroup", call_args[0][0].full_url)

    def test_main_sends_media_group_and_pins_first_message(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "PiliSuper.apk").write_bytes(b"x" * 1024)

            with (
                patch.dict(
                    os.environ,
                    {
                        "TELEGRAM_BOT_TOKEN": "test_token",
                        "TELEGRAM_CHAT_ID": "test_chat",
                        "GITHUB_REPOSITORY": "owner/repo",
                        "GITHUB_SHA": "abc123",
                    },
                ),
                patch.object(
                    sys, "argv", ["notify_telegram.py", "--output", str(output), "--release-tag", "v2.1.0-beta"]
                ),
                patch("urllib.request.urlopen") as urlopen_mock,
            ):
                urlopen_mock.return_value.__enter__.return_value.read.return_value = (
                    b'{"ok": true, "result": [{"message_id": 123}]}'
                )
                notify_telegram.main()

                calls = [call[0][0].full_url for call in urlopen_mock.call_args_list]
                media_group_calls = [c for c in calls if "sendMediaGroup" in c]
                pin_calls = [c for c in calls if "pinChatMessage" in c]

                self.assertEqual(len(media_group_calls), 1)
                self.assertEqual(len(pin_calls), 1)


if __name__ == "__main__":
    unittest.main()
