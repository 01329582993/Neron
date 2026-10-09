"""Exhaustive tests for Stage 15: Cross-Platform Packaging, PyInstaller, InnoSetup, AppImage, Debian, and Offline Bundles."""

import json
from pathlib import Path

import pytest
import yaml

from neron.packaging import (
    LinuxPackager,
    OfflineBundleGenerator,
    PackageBuilder,
    PackagingConfig,
    PyInstallerSpecGenerator,
    WindowsPackager,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PackagingConfig Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPackagingConfig:

    def test_default_config_values(self):
        cfg = PackagingConfig()
        assert cfg.app_name == "Neron"
        assert cfg.version == "1.0.0"
        assert cfg.target_os == "auto"
        assert "neron" in cfg.hidden_imports
        assert "psutil" in cfg.hidden_imports

    def test_resolved_target_os(self):
        cfg_win = PackagingConfig(target_os="windows")
        assert cfg_win.get_resolved_target_os() == "windows"

        cfg_linux = PackagingConfig(target_os="linux")
        assert cfg_linux.get_resolved_target_os() == "linux"

        cfg_auto = PackagingConfig(target_os="auto")
        assert cfg_auto.get_resolved_target_os() in ("windows", "linux", "macos")

    def test_config_to_dict(self):
        cfg = PackagingConfig(app_name="CustomNeron", version="2.0.0")
        data = cfg.to_dict()
        assert data["app_name"] == "CustomNeron"
        assert data["version"] == "2.0.0"
        assert "target_os" in data


# ─────────────────────────────────────────────────────────────────────────────
# 2. PyInstallerSpecGenerator Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPyInstallerSpecGenerator:

    def test_generate_spec_content(self, tmp_path):
        cfg = PackagingConfig(app_name="Neron", version="1.0.0", entrypoint="neron/__main__.py")
        content = PyInstallerSpecGenerator.generate_spec_content(cfg, project_root=tmp_path)

        assert "Analysis(" in content
        assert "PYZ(" in content
        assert "EXE(" in content
        assert "neron" in content
        assert "hiddenimports=" in content
        assert "psutil" in content

    def test_write_spec_file(self, tmp_path):
        cfg = PackagingConfig()
        spec_path = tmp_path / "neron.spec"
        out = PyInstallerSpecGenerator.write_spec_file(cfg, spec_path, project_root=tmp_path)

        assert out.is_file()
        assert "block_cipher = None" in out.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 3. WindowsPackager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWindowsPackager:

    def test_generate_inno_setup_script(self):
        cfg = PackagingConfig(app_name="Neron", version="1.0.0", author="Neron AI")
        iss = WindowsPackager.generate_inno_setup_script(cfg)

        assert '#define MyAppName "Neron"' in iss
        assert '#define MyAppVersion "1.0.0"' in iss
        assert "OutputBaseFilename=Neron-Setup-v1.0.0" in iss
        assert "[Setup]" in iss
        assert "[Files]" in iss
        assert "[Icons]" in iss
        assert "[Run]" in iss

    def test_write_inno_setup_file(self, tmp_path):
        cfg = PackagingConfig()
        out_iss = tmp_path / "installer.iss"
        res = WindowsPackager.write_inno_setup_file(cfg, out_iss)

        assert res.is_file()
        assert "MyAppName" in res.read_text(encoding="utf-8")

    def test_get_pyinstaller_build_command(self, tmp_path):
        spec = tmp_path / "test.spec"
        cmd = WindowsPackager.get_pyinstaller_build_command(spec, dist_dir=tmp_path / "dist")

        assert "PyInstaller" in cmd
        assert str(spec.resolve()) in cmd
        assert "--noconfirm" in cmd
        assert "--distpath" in cmd


# ─────────────────────────────────────────────────────────────────────────────
# 4. LinuxPackager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLinuxPackager:

    def test_create_appimage_structure(self, tmp_path):
        cfg = PackagingConfig(app_name="Neron", version="1.0.0")
        tree = LinuxPackager.create_appimage_structure(cfg, tmp_path)

        assert tree["app_dir"].is_dir()
        assert tree["apprun"].is_file()
        assert tree["desktop"].is_file()
        assert tree["icon"].is_file()

        apprun_txt = tree["apprun"].read_text(encoding="utf-8")
        assert "AppRun entrypoint" in apprun_txt
        assert "LD_LIBRARY_PATH" in apprun_txt

        desktop_txt = tree["desktop"].read_text(encoding="utf-8")
        assert "[Desktop Entry]" in desktop_txt
        assert "Name=Neron" in desktop_txt
        assert "Exec=neron" in desktop_txt

    def test_create_debian_package_structure(self, tmp_path):
        cfg = PackagingConfig(app_name="Neron", version="1.0.0", author="Neron Team")
        tree = LinuxPackager.create_debian_package_structure(cfg, tmp_path)

        assert tree["deb_dir"].is_dir()
        assert tree["control"].is_file()
        assert tree["postinst"].is_file()
        assert tree["prerm"].is_file()

        control_txt = tree["control"].read_text(encoding="utf-8")
        assert "Package: neron" in control_txt
        assert "Version: 1.0.0" in control_txt
        assert "Maintainer: Neron Team" in control_txt

        postinst_txt = tree["postinst"].read_text(encoding="utf-8")
        assert "ln -sf" in postinst_txt


# ─────────────────────────────────────────────────────────────────────────────
# 5. OfflineBundleGenerator Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOfflineBundleGenerator:

    def test_create_offline_bundle(self, tmp_path):
        cfg = PackagingConfig(app_name="Neron", version="1.0.0")
        res = OfflineBundleGenerator.create_offline_bundle(cfg, output_dir=tmp_path)

        assert res["bundle_dir"].is_dir()
        assert res["manifest_file"].is_file()
        assert res["config_file"].is_file()
        assert res["win_script"].is_file()
        assert res["linux_script"].is_file()
        assert res["files_count"] >= 4

        # Verify offline configuration
        cfg_data = yaml.safe_load(res["config_file"].read_text(encoding="utf-8"))
        assert cfg_data["offline_mode"] is True
        assert cfg_data["ai"]["router"]["offline_first"] is True

        # Verify SHA256 integrity manifest
        manifest = json.loads(res["manifest_file"].read_text(encoding="utf-8"))
        assert manifest["app_name"] == "Neron"
        assert manifest["version"] == "1.0.0"
        assert manifest["offline_ready"] is True
        assert len(manifest["files"]) >= 4

        # Verify checksum matches for config file
        rel_cfg = "config/neron.yaml"
        assert rel_cfg in manifest["files"]
        calculated_sha = OfflineBundleGenerator.calculate_sha256(res["config_file"])
        assert manifest["files"][rel_cfg] == calculated_sha


# ─────────────────────────────────────────────────────────────────────────────
# 6. PackageBuilder Facade Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPackageBuilder:

    def test_build_windows_artifacts(self, tmp_path):
        builder = PackageBuilder(project_root=tmp_path)
        cfg = PackagingConfig()
        out = builder.build_windows_artifacts(cfg, tmp_path / "win_out")

        assert out["status"] == "success"
        assert out["spec_file"].is_file()
        assert out["inno_setup_file"].is_file()

    def test_build_linux_artifacts(self, tmp_path):
        builder = PackageBuilder(project_root=tmp_path)
        cfg = PackagingConfig()
        out = builder.build_linux_artifacts(cfg, tmp_path / "linux_out")

        assert out["status"] == "success"
        assert out["appimage_dir"].is_dir()
        assert out["debian_dir"].is_dir()

    def test_build_offline_bundle(self, tmp_path):
        builder = PackageBuilder(project_root=tmp_path)
        cfg = PackagingConfig()
        out = builder.build_offline_bundle(cfg, tmp_path / "offline_out")

        assert out["bundle_dir"].is_dir()
        assert out["manifest_file"].is_file()
