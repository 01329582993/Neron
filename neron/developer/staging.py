"""Isolated staging workspace creator and diff tracker for Neron self-updates."""

from pathlib import Path
import shutil
from typing import Dict, List, Optional, Union

from neron.developer.patcher import PatchGenerator
from neron.utils.logger import get_logger

logger = get_logger("developer.staging")


class StagingWorkspace:
    """
    Manages an isolated directory workspace (.neron/staging/workspace/)
    where code modifications are written and validated before deployment.
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        production_root: Optional[Union[str, Path]] = None,
    ):
        self.production_root = Path(production_root).resolve() if production_root else Path.cwd().resolve()
        staging_parent = Path(base_dir).resolve() if base_dir else (self.production_root / ".neron" / "staging")
        self.workspace_dir = staging_parent / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def prepare(self) -> None:
        """Initialize or reset the staging workspace directory."""
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Staging workspace initialized at: {self.workspace_dir}")

    def stage_file(self, rel_path: Union[str, Path], content: str) -> Path:
        """
        Stage a file modification in the isolated workspace.

        Args:
            rel_path: Relative path from project root (e.g. 'neron/utils/helper.py')
            content: Complete new content for the file.
        """
        clean_rel = Path(rel_path)
        if clean_rel.is_absolute():
            try:
                clean_rel = clean_rel.relative_to(self.production_root)
            except ValueError:
                # If outside production root, use its relative parts
                clean_rel = Path(*clean_rel.parts[1:])

        dest_file = self.workspace_dir / clean_rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(content, encoding="utf-8")
        logger.info(f"Staged file: {clean_rel} -> {dest_file}")
        return dest_file

    def get_staged_files(self) -> List[str]:
        """Return list of relative paths of all currently staged files."""
        if not self.workspace_dir.exists():
            return []

        rel_paths = []
        for p in self.workspace_dir.rglob("*"):
            if p.is_file():
                rel_paths.append(str(p.relative_to(self.workspace_dir)).replace("\\", "/"))
        return sorted(rel_paths)

    def read_staged_file(self, rel_path: Union[str, Path]) -> Optional[str]:
        """Read content of a staged file by its relative path."""
        p = self.workspace_dir / rel_path
        if not p.is_file():
            return None
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return p.read_text(encoding="latin-1", errors="replace")

    def get_diff_summary(self) -> Dict[str, str]:
        """
        Compute unified diffs for all staged files against production workspace.

        Returns:
            Dictionary mapping relative file path to unified diff string.
        """
        diffs = {}
        for rel_str in self.get_staged_files():
            staged_content = self.read_staged_file(rel_str) or ""
            prod_path = self.production_root / rel_str
            prod_content = ""
            if prod_path.is_file():
                try:
                    prod_content = prod_path.read_text(encoding="utf-8")
                except Exception:
                    prod_content = prod_path.read_text(encoding="latin-1", errors="replace")

            diff = PatchGenerator.generate_diff(
                original_text=prod_content,
                modified_text=staged_content,
                filename=rel_str,
            )
            diffs[rel_str] = diff
        return diffs

    def clear(self) -> None:
        """Remove all staged files and clean up workspace."""
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Staging workspace cleared.")
