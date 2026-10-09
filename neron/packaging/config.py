"""Configuration models for cross-platform packaging and distribution."""

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union


@dataclass
class PackagingConfig:
    """Settings governing binary packaging, installer creation, and offline bundles."""
    app_name: str = "Neron"
    version: str = "1.0.0"
    author: str = "Neron Team"
    description: str = "Modular Local-First AI Computer Agent"
    entrypoint: str = "neron/__main__.py"
    target_os: str = "auto"
    bundle_type: str = "standalone"
    output_dir: Optional[Union[str, Path]] = None
    icon_path: Optional[str] = None
    include_models: bool = False
    models_dir: Optional[Union[str, Path]] = None
    hidden_imports: List[str] = field(default_factory=lambda: [
        "neron",
        "psutil",
        "yaml",
        "requests",
        "bs4",
        "sqlite3",
        "rich",
    ])

    def get_resolved_target_os(self) -> str:
        """Resolve 'auto' target OS to current platform."""
        if self.target_os != "auto":
            return self.target_os.lower()
        if sys.platform.startswith("win"):
            return "windows"
        elif sys.platform.startswith("darwin"):
            return "macos"
        return "linux"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "target_os": self.get_resolved_target_os(),
            "bundle_type": self.bundle_type,
            "include_models": self.include_models,
            "hidden_imports_count": len(self.hidden_imports),
        }
