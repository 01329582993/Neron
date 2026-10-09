"""PyInstaller specification generator for standalone binary packaging."""

from pathlib import Path
from typing import Optional, Union

from neron.packaging.config import PackagingConfig


class PyInstallerSpecGenerator:
    """
    Generates tailored, reproducible PyInstaller .spec files for Neron.
    """

    @classmethod
    def generate_spec_content(
        cls,
        config: PackagingConfig,
        project_root: Optional[Union[str, Path]] = None,
    ) -> str:
        root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
        entry_file = (root / config.entrypoint).resolve()

        hidden_imports_repr = repr(config.hidden_imports)
        datas_list = [
            (str(root / "config"), "config"),
            (str(root / "plugins"), "plugins"),
        ]
        datas_repr = repr([(d[0].replace("\\", "/"), d[1]) for d in datas_list if Path(d[0]).exists()])

        icon_option = f"icon='{config.icon_path.replace(chr(92), '/')}'," if config.icon_path else ""

        spec_template = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec for {config.app_name} v{config.version}

block_cipher = None

a = Analysis(
    ['{str(entry_file).replace(chr(92), "/")}'],
    pathex=['{str(root).replace(chr(92), "/")}'],
    binaries=[],
    datas={datas_repr},
    hiddenimports={hidden_imports_repr},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{config.app_name.lower()}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_option}
)
'''
        return spec_template

    @classmethod
    def write_spec_file(
        cls,
        config: PackagingConfig,
        output_file: Union[str, Path],
        project_root: Optional[Union[str, Path]] = None,
    ) -> Path:
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = cls.generate_spec_content(config, project_root=project_root)
        out_path.write_text(content, encoding="utf-8")
        return out_path
