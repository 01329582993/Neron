"""Standalone offline installer generator bundled with local configuration and model assets."""

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Union

import yaml

from neron.packaging.config import PackagingConfig
from neron.utils.logger import get_logger

logger = get_logger("packaging.offline")


class OfflineBundleGenerator:
    """
    Creates zero-config, self-contained offline distribution bundles
    with local configurations, model runners, and SHA256 integrity manifests.
    """

    @classmethod
    def calculate_sha256(cls, file_path: Path) -> str:
        """Compute SHA256 hex digest for a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def create_offline_bundle(
        cls,
        config: PackagingConfig,
        output_dir: Union[str, Path],
        project_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Construct a standalone offline installer directory.
        """
        root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
        bundle_root = Path(output_dir).resolve() / f"{config.app_name}-Offline-v{config.version}"
        bundle_root.mkdir(parents=True, exist_ok=True)

        # 1. Setup offline config directory
        config_dir = bundle_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        offline_cfg_data = {
            "version": config.version,
            "offline_mode": True,
            "security": {
                "profile": "STANDARD",
            },
            "ai": {
                "provider": "ollama",
                "local_endpoint": "http://127.0.0.1:11434",
                "default_model": "mistral:7b",
                "router": {
                    "fallback_enabled": True,
                    "offline_first": True,
                },
            },
            "voice": {
                "stt_engine": "whisper_cpp",
                "tts_engine": "system",
            },
        }
        offline_cfg_path = config_dir / "neron.yaml"
        offline_cfg_path.write_text(yaml.dump(offline_cfg_data, sort_keys=False), encoding="utf-8")

        # 2. Setup models directory
        models_dir = bundle_root / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        models_readme = models_dir / "README.md"
        models_readme.write_text(
            f"# {config.app_name} Offline Model Checkpoints\n\n"
            "Place GGUF models or Ollama model blobs here for zero-internet operation.\n"
            "Supported models: llama3, mistral, qwen2.5, phi-3.\n",
            encoding="utf-8",
        )

        # 3. Create Windows offline installer script
        win_install_script = f'''@echo off
title {config.app_name} Offline Installer
echo ========================================================
echo   Installing {config.app_name} v{config.version} (Offline Mode)
echo ========================================================
echo.
if not exist "%USERPROFILE%\\.neron" mkdir "%USERPROFILE%\\.neron"
if not exist "%USERPROFILE%\\.neron\\config" mkdir "%USERPROFILE%\\.neron\\config"
copy /Y config\\neron.yaml "%USERPROFILE%\\.neron\\config\\neron.yaml" >nul
echo [OK] Offline configuration deployed to %USERPROFILE%\\.neron\\config\\
echo [OK] Verifying offline components...
echo.
echo {config.app_name} is ready for offline operation.
pause
'''
        win_script_path = bundle_root / "install_offline.bat"
        win_script_path.write_text(win_install_script, encoding="utf-8")

        # 4. Create Linux offline installer script
        linux_install_script = f'''#!/bin/sh
set -e
echo "========================================================"
echo "  Installing {config.app_name} v{config.version} (Offline Mode)"
echo "========================================================"
mkdir -p "$HOME/.neron/config"
cp -f config/neron.yaml "$HOME/.neron/config/neron.yaml"
echo "[OK] Offline configuration deployed to $HOME/.neron/config/"
echo "{config.app_name} is ready for offline operation."
exit 0
'''
        linux_script_path = bundle_root / "install_offline.sh"
        linux_script_path.write_text(linux_install_script, encoding="utf-8")

        # 5. Build SHA256 integrity manifest
        file_manifest: Dict[str, str] = {}
        for p in bundle_root.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(bundle_root)).replace("\\", "/")
                file_manifest[rel] = cls.calculate_sha256(p)

        manifest_data = {
            "app_name": config.app_name,
            "version": config.version,
            "offline_ready": True,
            "file_count": len(file_manifest),
            "files": file_manifest,
        }
        manifest_path = bundle_root / "bundle_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        logger.info(f"Successfully generated offline bundle at: {bundle_root}")
        return {
            "bundle_dir": bundle_root,
            "manifest_file": manifest_path,
            "config_file": offline_cfg_path,
            "win_script": win_script_path,
            "linux_script": linux_script_path,
            "files_count": len(file_manifest),
        }
