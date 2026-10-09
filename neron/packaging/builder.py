"""PackageBuilder orchestrator coordinating multi-platform and offline builds."""

from pathlib import Path
from typing import Any, Dict, Optional, Union

from neron.packaging.config import PackagingConfig
from neron.packaging.linux import LinuxPackager
from neron.packaging.offline import OfflineBundleGenerator
from neron.packaging.spec import PyInstallerSpecGenerator
from neron.packaging.windows import WindowsPackager
from neron.utils.logger import get_logger

logger = get_logger("packaging.builder")


class PackageBuilder:
    """
    Unified entry point for generating distribution artifacts:
    Windows executables & installers, Linux AppImages & Debian packages, and offline bundles.
    """

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd().resolve()

    def build_windows_artifacts(
        self,
        config: PackagingConfig,
        output_dir: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Generate PyInstaller spec and InnoSetup script for Windows.
        """
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        spec_path = out / f"{config.app_name.lower()}.spec"
        PyInstallerSpecGenerator.write_spec_file(config, spec_path, project_root=self.project_root)

        iss_path = out / f"{config.app_name.lower()}_installer.iss"
        WindowsPackager.write_inno_setup_file(config, iss_path, dist_dir=out / "dist")

        cmd = WindowsPackager.get_pyinstaller_build_command(spec_path, dist_dir=out / "dist")

        return {
            "status": "success",
            "platform": "windows",
            "spec_file": spec_path,
            "inno_setup_file": iss_path,
            "build_command": cmd,
        }

    def build_linux_artifacts(
        self,
        config: PackagingConfig,
        output_dir: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Generate Linux AppImage AppDir structure and Debian package layout.
        """
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        appimage_tree = LinuxPackager.create_appimage_structure(config, out)
        debian_tree = LinuxPackager.create_debian_package_structure(config, out)

        return {
            "status": "success",
            "platform": "linux",
            "appimage_dir": appimage_tree["app_dir"],
            "debian_dir": debian_tree["deb_dir"],
        }

    def build_offline_bundle(
        self,
        config: PackagingConfig,
        output_dir: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Generate self-contained offline installer archive.
        """
        return OfflineBundleGenerator.create_offline_bundle(
            config,
            output_dir=output_dir,
            project_root=self.project_root,
        )
