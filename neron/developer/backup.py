"""Atomic backup snapshotting and instant rollback engine for Neron."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional, Union

from neron.utils.logger import get_logger

logger = get_logger("developer.backup")


@dataclass
class BackupMetadata:
    """Metadata describing a backup snapshot."""
    backup_id: str
    timestamp: str
    files: List[str]
    description: str = "Pre-deployment checkpoint"
    is_restored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "timestamp": self.timestamp,
            "files": self.files,
            "description": self.description,
            "is_restored": self.is_restored,
        }


class BackupManager:
    """
    Creates and restores timestamped backup checkpoints in .neron/backups/
    to guarantee safe, one-click rollback on any self-update failure.
    """

    def __init__(
        self,
        backup_root: Optional[Union[str, Path]] = None,
        production_root: Optional[Union[str, Path]] = None,
    ):
        self.production_root = Path(production_root).resolve() if production_root else Path.cwd().resolve()
        self.backup_root = Path(backup_root).resolve() if backup_root else (self.production_root / ".neron" / "backups")
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        rel_files: List[str],
        description: str = "Pre-deployment snapshot",
    ) -> str:
        """
        Backup the specified files from production into a timestamped directory.

        Returns:
            The unique backup_id string.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        sub_id = time.time_ns() % 1_000_000   # microsecond uniqueness — 6 digits
        backup_id = f"backup_{ts}_{sub_id:06d}"
        dest_dir = self.backup_root / backup_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []
        for rel_str in rel_files:
            clean_rel = Path(rel_str.replace("\\", "/"))
            src_path = self.production_root / clean_rel
            if src_path.is_file():
                dest_file = dest_dir / clean_rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_file)
                copied_files.append(str(clean_rel).replace("\\", "/"))

        meta = BackupMetadata(
            backup_id=backup_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            files=copied_files,
            description=description,
        )

        meta_path = dest_dir / "backup_meta.json"
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")
        logger.info(f"Created backup '{backup_id}' with {len(copied_files)} files at {dest_dir}")
        return backup_id

    def restore_backup(self, backup_id: Optional[str] = None) -> bool:
        """
        Restore files from a backup snapshot back into production.
        If backup_id is None, restores the most recent backup snapshot.
        """
        target_id = backup_id or self.get_latest_backup_id()
        if not target_id:
            logger.warning("No backup snapshot available to restore.")
            return False

        target_dir = self.backup_root / target_id
        if not target_dir.is_dir():
            raise FileNotFoundError(f"Backup snapshot '{target_id}' not found at {target_dir}")

        meta_path = target_dir / "backup_meta.json"
        files_to_restore = []
        if meta_path.is_file():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                files_to_restore = data.get("files", [])
            except Exception as e:
                logger.warning(f"Could not read backup_meta.json: {e}")

        # If meta has explicit files, restore them
        if files_to_restore:
            for rel_str in files_to_restore:
                src_file = target_dir / rel_str
                dest_file = self.production_root / rel_str
                if src_file.is_file():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)
        else:
            # Fallback: copy everything except backup_meta.json
            for p in target_dir.rglob("*"):
                if p.is_file() and p.name != "backup_meta.json":
                    rel = p.relative_to(target_dir)
                    dest_file = self.production_root / rel
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dest_file)

        # Mark restored in meta
        if meta_path.is_file():
            try:
                data["is_restored"] = True
                meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

        logger.info(f"Successfully restored production files from backup '{target_id}'")
        return True

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backup snapshots ordered by newest first."""
        results = []
        for p in self.backup_root.iterdir():
            if p.is_dir() and p.name.startswith("backup_"):
                meta_file = p / "backup_meta.json"
                if meta_file.is_file():
                    try:
                        results.append(json.loads(meta_file.read_text(encoding="utf-8")))
                        continue
                    except Exception:
                        pass
                results.append({
                    "backup_id": p.name,
                    "timestamp": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "files": [],
                    "description": "Unindexed snapshot",
                    "is_restored": False,
                })

        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results

    def get_latest_backup_id(self) -> Optional[str]:
        """Return the backup_id of the most recently created backup."""
        backups = self.list_backups()
        return backups[0]["backup_id"] if backups else None
