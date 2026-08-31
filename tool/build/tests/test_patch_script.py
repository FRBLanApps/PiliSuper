import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BUILD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD_ROOT))

patch_script = importlib.import_module("patch")


class PatchTests(unittest.TestCase):
    def test_patch_sets_match_upstream_powershell_order(self):
        # Given
        expected_common = [
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

        # When
        patch_sets = (
            patch_script.COMMON_PATCHES,
            patch_script.ANDROID_PATCHES,
            patch_script.IOS_FLUTTER_PATCHES,
            patch_script.IOS_PROJECT_PATCHES,
        )

        # Then
        self.assertEqual(patch_sets[0], expected_common)
        self.assertEqual(
            patch_sets[1],
            ["bottom_sheet_android.patch", "scroll_view.patch", "navigator.patch"],
        )
        self.assertEqual(
            patch_sets[2],
            ["scroll_view.patch", "bottom_sheet_ios_flutter.patch", "navigator.patch"],
        )
        self.assertEqual(
            patch_sets[3],
            ["bottom_sheet_ios_piliplus.patch", "geetest_ios.patch"],
        )

    def test_common_patch_set_includes_material_dependencies(self):
        self.assertEqual(
            patch_script.COMMON_PATCHES[-3:],
            ["text_painter.patch", "sliver.patch", "refresh_indicator.patch"],
        )

    def test_sdk_patch_plan_matches_platform_reset_rules(self):
        self.assertTrue(patch_script.should_reset_flutter_sdk("android"))
        self.assertTrue(patch_script.should_reset_flutter_sdk("linux"))
        self.assertTrue(patch_script.should_reset_flutter_sdk("all"))
        self.assertFalse(patch_script.should_reset_flutter_sdk("ios"))
        self.assertFalse(patch_script.should_reset_flutter_sdk("macos"))
        self.assertFalse(patch_script.should_reset_flutter_sdk("windows"))

    def test_material_patch_plan_matches_platform_order(self):
        self.assertEqual(
            patch_script.material_patch_names("android")[-1],
            "bottom_sheet_android.patch",
        )
        self.assertEqual(
            patch_script.material_patch_names("ios")[-1],
            "bottom_sheet_ios_flutter_material.patch",
        )
        self.assertEqual(
            patch_script.material_patch_names("linux"),
            patch_script.MATERIAL_PATCHES,
        )

    def test_sdk_patch_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "modal_barrier.patch").write_bytes(b"")
            with patch.object(
                patch_script,
                "run_command",
                side_effect=subprocess.CalledProcessError(1, "git"),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    patch_script.apply_sdk_patches(
                        ["modal_barrier.patch"], Path(temp), Path("flutter")
                    )

    def test_all_selected_patch_payloads_exist(self):
        # Given
        patch_dir = BUILD_ROOT.parent / "patches"
        patch_names = {
            *patch_script.COMMON_PATCHES,
            *patch_script.ANDROID_PATCHES,
            *patch_script.IOS_FLUTTER_PATCHES,
            *patch_script.IOS_PROJECT_PATCHES,
        }

        # When
        missing = sorted(name for name in patch_names if not (patch_dir / name).is_file())

        # Then
        self.assertEqual(missing, [])

    def test_material_ui_patch_sets_are_platform_specific(self):
        self.assertEqual(
            patch_script.MATERIAL_COMMON_PATCHES,
            [
                "modal_barrier_material.patch",
                "navigation_drawer.patch",
                "popup_menu.patch",
                "fab.patch",
                "text_field.patch",
                "scaffold.patch",
                "refresh_indicator.patch",
                "tabs.patch",
            ],
        )
        self.assertEqual(patch_script.MATERIAL_ANDROID_PATCHES, ["bottom_sheet_android.patch"])
        self.assertEqual(
            patch_script.MATERIAL_IOS_PATCHES,
            ["bottom_sheet_ios_flutter_material.patch"],
        )

    def test_material_ui_dir_selects_latest_cache_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            hosted = Path(temp) / "hosted" / "pub.dev"
            hosted.mkdir(parents=True)
            (hosted / "material_ui-1.0.0").mkdir()
            latest = hosted / "material_ui-1.1.0"
            latest.mkdir()

            self.assertEqual(patch_script.material_ui_dir(Path(temp)), latest)

    def test_cupertino_ui_dir_selects_latest_cache_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            hosted = Path(temp) / "hosted" / "pub.dev"
            hosted.mkdir(parents=True)
            (hosted / "cupertino_ui-1.0.0").mkdir()
            latest = hosted / "cupertino_ui-1.1.0"
            latest.mkdir()

            self.assertEqual(patch_script.cupertino_ui_dir(Path(temp)), latest)

    def test_cupertino_ui_patch_sets_are_ios_only(self):
        self.assertEqual(patch_script.CUPERTINO_COMMON_PATCHES, [])
        self.assertEqual(
            patch_script.CUPERTINO_IOS_PATCHES,
            ["bottom_sheet_ios_flutter.patch"],
        )
        self.assertEqual(
            patch_script.cupertino_patch_names("ios"),
            ["bottom_sheet_ios_flutter.patch"],
        )
        self.assertEqual(
            patch_script.cupertino_patch_names("all"),
            ["bottom_sheet_ios_flutter.patch"],
        )
        for platform in ("android", "linux", "macos", "windows"):
            self.assertEqual(patch_script.cupertino_patch_names(platform), [])

    def test_cupertino_patch_payloads_exist(self):
        cupertino_dir = BUILD_ROOT.parent / "patches" / "cupertino"
        missing = sorted(
            name
            for name in (
                *patch_script.CUPERTINO_COMMON_PATCHES,
                *patch_script.CUPERTINO_IOS_PATCHES,
            )
            if not (cupertino_dir / name).is_file()
        )

        self.assertEqual(missing, [])

    def test_cupertino_patches_require_pub_cache_package(self):
        with patch.object(patch_script, "cupertino_ui_dir", return_value=None):
            with self.assertRaises(SystemExit):
                patch_script.apply_cupertino_patches("ios", Path("tool/patches"))

    def test_material_patch_line_endings_are_normalized(self):
        with tempfile.TemporaryDirectory() as temp:
            crlf_patch = Path(temp) / "scaffold.patch"
            crlf_patch.write_bytes(b"--- a\r\n+++ b\r\n@@ -1 +1 @@\r\n")
            lf_patch = Path(temp) / "tabs.patch"
            lf_patch.write_bytes(b"--- a\n+++ b\n")
            unrelated = Path(temp) / "notes.txt"
            unrelated.write_bytes(b"crlf\r\nuntouched\r\n")

            patch_script.normalize_patch_line_endings(Path(temp))

            self.assertEqual(
                crlf_patch.read_bytes(), b"--- a\n+++ b\n@@ -1 +1 @@\n"
            )
            self.assertEqual(lf_patch.read_bytes(), b"--- a\n+++ b\n")
            self.assertEqual(unrelated.read_bytes(), b"crlf\r\nuntouched\r\n")

    def test_already_applied_project_patch_is_accepted(self):
        completed = type("Completed", (), {"returncode": 0})()
        with patch.object(
            patch_script,
            "run_command",
            side_effect=[type("Completed", (), {"returncode": 1})(), completed],
        ) as run:
            patch_script.apply_project_patch(Path("patch.diff"), Path("."))

        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
