"""Code introspection and AST parsing subsystem for Neron."""

import ast
import importlib.util
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from neron.utils.logger import get_logger

logger = get_logger("developer.introspector")


class CodeIntrospector:
    """
    Analyzes Python source code, extracts syntax structures via AST,
    and inspects classes, functions, docstrings, and imports.
    """

    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        self.root_dir = Path(root_dir).resolve() if root_dir else Path.cwd().resolve()

    def validate_syntax(self, code: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate Python code syntax without executing it.

        Returns:
            (is_valid, error_message, line_number)
        """
        if not code or not code.strip():
            return True, None, None

        try:
            ast.parse(code)
            return True, None, None
        except SyntaxError as e:
            return False, e.msg, e.lineno
        except Exception as e:
            return False, str(e), None

    def inspect_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Inspect a Python file and extract classes, functions, imports, and docstring.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        lines = content.splitlines()
        total_lines = len(lines)

        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError as e:
            return {
                "file_path": str(path),
                "is_valid_syntax": False,
                "syntax_error": f"Line {e.lineno}: {e.msg}",
                "total_lines": total_lines,
                "classes": [],
                "functions": [],
                "imports": [],
                "module_docstring": None,
            }

        module_docstring = ast.get_docstring(tree)
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []
        imports: List[str] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(self._extract_class_info(node, lines))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._extract_function_info(node, lines))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}" if mod else alias.name)

        return {
            "file_path": str(path),
            "is_valid_syntax": True,
            "syntax_error": None,
            "total_lines": total_lines,
            "module_docstring": module_docstring,
            "classes": classes,
            "functions": functions,
            "imports": imports,
        }

    def inspect_module(self, module_name: str) -> Dict[str, Any]:
        """
        Locate and inspect a Python module by qualified name (e.g. 'neron.security.policy').
        """
        # Try importlib spec resolution first
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.origin and Path(spec.origin).is_file():
                return self.inspect_file(spec.origin)
        except Exception as e:
            logger.debug(f"find_spec failed for {module_name}: {e}")

        # Fallback: search relative to root_dir
        rel_parts = module_name.split(".")
        candidates = [
            self.root_dir.joinpath(*rel_parts).with_suffix(".py"),
            self.root_dir.joinpath(*rel_parts, "__init__.py"),
            self.root_dir / "neron" / Path(*rel_parts[1:]).with_suffix(".py") if rel_parts[0] == "neron" else None,
        ]

        for cand in candidates:
            if cand and cand.is_file():
                return self.inspect_file(cand)

        raise ModuleNotFoundError(f"Could not locate module source for '{module_name}'")

    def find_symbol(
        self,
        symbol_name: str,
        search_dir: Optional[Union[str, Path]] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for class or function definitions matching symbol_name across Python files.
        """
        target_dir = Path(search_dir).resolve() if search_dir else self.root_dir
        results: List[Dict[str, Any]] = []

        if not target_dir.is_dir():
            return results

        for py_path in target_dir.rglob("*.py"):
            # Skip virtual environments and hidden dirs
            parts = py_path.parts
            if any(p.startswith(".") or p in ("venv", ".venv", "__pycache__", "build", "dist") for p in parts):
                continue

            try:
                content = py_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_path))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == symbol_name:
                    results.append({
                        "symbol": symbol_name,
                        "type": "class",
                        "file_path": str(py_path),
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node),
                    })
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol_name:
                    results.append({
                        "symbol": symbol_name,
                        "type": "function",
                        "file_path": str(py_path),
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, "end_lineno", node.lineno),
                        "docstring": ast.get_docstring(node),
                    })

                if len(results) >= max_results:
                    return results

        return results

    def get_source_lines(
        self,
        file_path: Union[str, Path],
        start_line: int,
        end_line: int,
    ) -> str:
        """
        Read source lines from a file (1-indexed, inclusive).
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        return "\n".join(lines[start_idx:end_idx])

    def _extract_class_info(self, node: ast.ClassDef, lines: List[str]) -> Dict[str, Any]:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{getattr(base.value, 'id', '')}.{base.attr}")

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function_info(item, lines))

        return {
            "name": node.name,
            "bases": bases,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "docstring": ast.get_docstring(node),
            "methods": methods,
        }

    def _extract_function_info(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        lines: List[str],
    ) -> Dict[str, Any]:
        args = [arg.arg for arg in node.args.args]
        return {
            "name": node.name,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "args": args,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "docstring": ast.get_docstring(node),
        }
