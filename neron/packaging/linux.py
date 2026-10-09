"""Linux distribution packager generating AppImage AppDirs and Debian control trees."""

from pathlib import Path
from typing import Dict, Optional, Union

from neron.packaging.config import PackagingConfig
from neron.utils.logger import get_logger

logger = get_logger("packaging.linux")


class LinuxPackager:
    """
    Constructs Linux AppImage directory layouts (AppDir) and Debian .deb packages.
    """

    @classmethod
    def create_appimage_structure(
        cls,
        config: PackagingConfig,
        target_dir: Union[str, Path],
    ) -> Dict[str, Path]:
        """
        Create standard Freedesktop AppDir tree for AppImage bundling.
        """
        app_dir = Path(target_dir).resolve() / f"{config.app_name}.AppDir"
        app_dir.mkdir(parents=True, exist_ok=True)
        usr_bin = app_dir / "usr" / "bin"
        usr_bin.mkdir(parents=True, exist_ok=True)

        # 1. AppRun executable launcher script
        apprun_script = f'''#!/bin/sh
# AppRun entrypoint for {config.app_name}
HERE="$(dirname "$(readlink -f "${{0}}")")"
export PATH="${{HERE}}/usr/bin:${{PATH}}"
export LD_LIBRARY_PATH="${{HERE}}/usr/lib:${{LD_LIBRARY_PATH}}"
export PYTHONHOME="${{HERE}}/usr"
exec "${{HERE}}/usr/bin/{config.app_name.lower()}" "$@"
'''
        apprun_path = app_dir / "AppRun"
        apprun_path.write_text(apprun_script, encoding="utf-8")

        # 2. Desktop file
        desktop_content = f'''[Desktop Entry]
Name={config.app_name}
Comment={config.description}
Exec={config.app_name.lower()}
Icon={config.app_name.lower()}
Terminal=true
Type=Application
Categories=Utility;Development;System;
StartupNotify=true
'''
        desktop_path = app_dir / f"{config.app_name.lower()}.desktop"
        desktop_path.write_text(desktop_content, encoding="utf-8")

        # 3. Icon placeholder
        icon_path = app_dir / f"{config.app_name.lower()}.png"
        if not icon_path.exists():
            icon_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        logger.info(f"Created Linux AppDir at: {app_dir}")
        return {
            "app_dir": app_dir,
            "apprun": apprun_path,
            "desktop": desktop_path,
            "icon": icon_path,
            "usr_bin": usr_bin,
        }

    @classmethod
    def create_debian_package_structure(
        cls,
        config: PackagingConfig,
        target_dir: Union[str, Path],
    ) -> Dict[str, Path]:
        """
        Construct standard Debian package build directory tree with DEBIAN/control.
        """
        deb_dir = Path(target_dir).resolve() / f"{config.app_name.lower()}_{config.version}_all"
        deb_dir.mkdir(parents=True, exist_ok=True)
        debian_meta_dir = deb_dir / "DEBIAN"
        debian_meta_dir.mkdir(parents=True, exist_ok=True)

        opt_dir = deb_dir / "opt" / config.app_name.lower()
        opt_dir.mkdir(parents=True, exist_ok=True)

        # 1. DEBIAN/control
        control_content = f'''Package: {config.app_name.lower()}
Version: {config.version}
Section: utils
Priority: optional
Architecture: all
Maintainer: {config.author} <team@neron.ai>
Depends: python3 (>= 3.10)
Description: {config.description}
 A local-first autonomous AI agent capable of operating the computer.
'''
        control_path = debian_meta_dir / "control"
        control_path.write_text(control_content, encoding="utf-8")

        # 2. DEBIAN/postinst script
        postinst_content = f'''#!/bin/sh
set -e
mkdir -p /usr/local/bin
ln -sf /opt/{config.app_name.lower()}/bin/{config.app_name.lower()} /usr/local/bin/{config.app_name.lower()}
exit 0
'''
        postinst_path = debian_meta_dir / "postinst"
        postinst_path.write_text(postinst_content, encoding="utf-8")

        # 3. DEBIAN/prerm script
        prerm_content = f'''#!/bin/sh
set -e
rm -f /usr/local/bin/{config.app_name.lower()}
exit 0
'''
        prerm_path = debian_meta_dir / "prerm"
        prerm_path.write_text(prerm_content, encoding="utf-8")

        logger.info(f"Created Debian package layout at: {deb_dir}")
        return {
            "deb_dir": deb_dir,
            "control": control_path,
            "postinst": postinst_path,
            "prerm": prerm_path,
            "opt_dir": opt_dir,
        }
