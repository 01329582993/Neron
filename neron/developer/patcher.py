"""Source code patch generation, diff calculation, and syntax validation for Neron."""

import ast
from dataclasses import dataclass, field
import difflib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from neron.security.policy import PermissionManager
from neron.utils.logger import get_logger

logger = get_logger("developer.patcher")


@dataclass
class PatchValidationResult:
    """Result of patch syntax and security validation."""
    is_valid: bool
    diff: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "diff": self.diff,
            "errors": self.errors,
            "warnings": self.warnings,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
        }


class PatchGenerator:
    """
    Computes unified diffs and applies patches to source files.
    """

    @staticmethod
    def generate_diff(
        original_text: str,
        modified_text: str,
        filename: str = "source.py",
    ) -> str:
        """
        Generate a unified diff between original and modified text.
        """
        orig_lines = original_text.splitlines(keepends=True)
        mod_lines = modified_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        return "".join(diff)

    @staticmethod
    def apply_patch(
        original_text: str,
        patch_diff: str,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Apply a unified diff patch to original text.

        Returns:
            (success, patched_text, error_message)
        """
        # Parse diff lines
        lines = patch_diff.splitlines()
        if not lines:
            return True, original_text, None

        # Check for unified diff header
        hunks = []
        current_hunk = None

        for line in lines:
            if line.startswith("@@"):
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {"header": line, "lines": []}
            elif current_hunk is not None:
                current_hunk["lines"].append(line)

        if current_hunk:
            hunks.append(current_hunk)

        if not hunks:
            return False, original_text, "No valid diff hunks found in patch."

        orig_lines = original_text.splitlines()
        result_lines = list(orig_lines)

        # Apply hunks (standard forward patch)
        offset = 0
        for hunk in hunks:
            header = hunk["header"]
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header)
            if not m:
                return False, original_text, f"Invalid hunk header format: {header}"

            orig_start = int(m.group(1)) - 1  # 0-indexed
            hunk_lines = hunk["lines"]

            # Verify and replace
            hunk_orig = [l[1:] for l in hunk_lines if l.startswith("-") or l.startswith(" ")]
            hunk_new = [l[1:] for l in hunk_lines if l.startswith("+") or l.startswith(" ")]

            target_idx = orig_start + offset
            # Validate matching context
            actual_orig = result_lines[target_idx : target_idx + len(hunk_orig)]
            if actual_orig != hunk_orig:
                # Fallback: search nearby lines
                found_idx = None
                for search_i in range(max(0, target_idx - 5), min(len(result_lines), target_idx + 6)):
                    if result_lines[search_i : search_i + len(hunk_orig)] == hunk_orig:
                        found_idx = search_i
                        break
                if found_idx is None:
                    return False, original_text, f"Patch hunk failed to match context around line {orig_start + 1}."
                target_idx = found_idx

            # Apply modification
            result_lines[target_idx : target_idx + len(hunk_orig)] = hunk_new
            offset += len(hunk_new) - len(hunk_orig)

        return True, "\n".join(result_lines), None


class PatchValidator:
    """
    Validates patches for syntax correctness, protected paths, and safety guardrails.
    """

    DANGEROUS_PATTERNS = [
        (re.compile(r"os\.system\s*\(\s*['\"]rm\s+-rf\s+/[*]?['\"]\s*\)"), "Critical: Root deletion command detected"),
        (re.compile(r"shutil\.rmtree\s*\(\s*['\"][/\\].*?['\"]\s*\)"), "Critical: Unbounded directory tree deletion"),
        (re.compile(r"subprocess\.call\s*\(\s*['\"]del\s+/[fF]\s+/[sS]\s+c:\\['\"]\s*\)"), "Critical: Windows root deletion command"),
    ]

    def __init__(self, protected_paths: Optional[List[str]] = None):
        self.protected_paths = protected_paths or PermissionManager.PROTECTED_SYSTEM_PATHS

    def validate_patch(
        self,
        target_file: Union[str, Path],
        modified_content: str,
        allow_syntax_errors: bool = False,
    ) -> PatchValidationResult:
        """
        Validate a proposed modification against a target file.
        """
        path = Path(target_file).resolve()
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Protected path check
        path_str = str(path).lower()
        for prot in self.protected_paths:
            if path_str.startswith(prot.lower()):
                errors.append(f"Cannot patch protected system path: {path}")
                break

        # 2. Syntax validation for Python files
        if path.suffix.lower() == ".py" and not allow_syntax_errors:
            try:
                ast.parse(modified_content, filename=path.name)
            except SyntaxError as e:
                errors.append(f"Python syntax error at line {e.lineno}: {e.msg}")
            except Exception as e:
                errors.append(f"AST validation failure: {e}")

        # 3. Dangerous patterns check
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if pattern.search(modified_content):
                errors.append(desc)

        # 4. Generate diff
        orig_text = ""
        if path.is_file():
            try:
                orig_text = path.read_text(encoding="utf-8")
            except Exception:
                orig_text = path.read_text(encoding="latin-1", errors="replace")

        diff = PatchGenerator.generate_diff(orig_text, modified_content, filename=path.name)

        # Count added/removed lines
        added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))

        if added > 500 or removed > 500:
            warnings.append(f"Large patch detected (+{added}/-{removed} lines). Exercise caution.")

        is_valid = len(errors) == 0

        return PatchValidationResult(
            is_valid=is_valid,
            diff=diff,
            errors=errors,
            warnings=warnings,
            added_lines=added,
            removed_lines=removed,
        )
