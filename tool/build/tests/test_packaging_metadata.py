import importlib
import sys
import tempfile
import unittest
from contextlib import chdir, nullcontext
from pathlib import Path
from unittest.mock import patch


BUILD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD_ROOT))
packaging = importlib.import_module("packaging")


class LinuxPackageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        binary = self.bundle / "PiliSuper"
        binary.write_bytes(b"binary")
        binary.chmod(0o755)
        (self.root / "assets/images/logo").mkdir(parents=True)
        (self.root / "assets/images/logo/logo.png").write_bytes(b"icon")
        self.identity = packaging.package_identity("org.frblanapps.pilisuper")

    def tearDown(self):
        self.temp.cleanup()

    def test_deb_metadata_declares_webkit_runtime(self):
        # Given
        control = self.root / "control-output"

        def capture_command(command, **kwargs):
            control.write_text((Path(command[-2]) / "DEBIAN/control").read_text())

        # When
        with chdir(self.root), patch.object(packaging, "require_command"), patch.object(
            packaging, "run_command", side_effect=capture_command
        ):
            packaging.package_deb(
                self.bundle, self.root / "out.deb", "PiliSuper", "x64", "1.2.3", self.identity
            )

        # Then
        self.assertIn("libwebkit2gtk-4.1-0", control.read_text())

    def test_rpm_metadata_declares_webkit_runtime(self):
        # Given
        spec = self.root / "spec-output"

        def capture_command(command, **kwargs):
            if command[0] == "tar":
                return nullcontext()
            spec.write_text(Path(command[-1]).read_text())
            rpm_dir = Path(command[command.index("--define") + 1].split(maxsplit=1)[1]) / "RPMS/x86_64"
            rpm_dir.mkdir(parents=True)
            rpm = rpm_dir / "pilisuper.rpm"
            rpm.write_bytes(b"rpm")

        # When
        with chdir(self.root), patch.object(packaging, "require_command"), patch.object(
            packaging, "run_command", side_effect=capture_command
        ):
            packaging.package_rpm(
                self.bundle, self.root / "out.rpm", "PiliSuper", "x64", "1.2.3", self.identity
            )

        # Then
        self.assertIn("webkit2gtk4.1", spec.read_text())

    def test_arch_metadata_declares_webkit_runtime(self):
        # Given
        pkgbuild = self.root / "pkgbuild-output"

        def capture_command(command, **kwargs):
            if command[0] == "tar":
                Path(command[2]).write_bytes(b"archive")
            elif command[0] == "makepkg":
                pkgbuild.write_text((kwargs["cwd"] / "PKGBUILD").read_text())
                (kwargs["cwd"] / "pilisuper-1.2.3.pkg.tar.zst").write_bytes(b"package")

        # When
        with chdir(self.root), patch.object(packaging, "require_command"), patch.object(
            packaging, "run_command", side_effect=capture_command
        ):
            packaging.package_arch(
                self.bundle, self.root / "out.pkg.tar.zst", "PiliSuper", "x64", "1.2.3", self.identity
            )

        # Then
        self.assertIn("webkit2gtk-4.1", pkgbuild.read_text())

    def test_ci_patches_linux_sdk_before_analysis(self):
        # Given
        workflow = (BUILD_ROOT.parents[1] / ".github/workflows/ci-check.yml").read_text()

        # When
        steps = workflow.split("      - name:")
        patch_step = next(index for index, step in enumerate(steps) if "patch.py linux" in step)
        analyze_step = next(index for index, step in enumerate(steps) if "flutter analyze" in step)

        # Then
        self.assertLess(patch_step, analyze_step)

    def test_linux_build_installs_webkit_development_package(self):
        # Given
        workflow = (BUILD_ROOT.parents[1] / ".github/workflows/build.yml").read_text()

        # When
        install = workflow.split("- name: Install system dependencies", 1)[1].split("- uses:", 1)[0]

        # Then
        self.assertIn("libwebkit2gtk-4.1-dev", install)
        self.assertNotIn("webkit2gtk-4.1 \\", install)


if __name__ == "__main__":
    unittest.main()
