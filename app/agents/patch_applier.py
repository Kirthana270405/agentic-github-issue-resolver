
import ast
import os
import re
import tempfile
from pathlib import Path

from app.agents.code_generator import GeneratedChange


class PatchApplier:
    def apply(
        self,
        change: GeneratedChange,
        repo_root: str | Path | None = None,
    ) -> tuple[bool, str]:
        """Safely apply an exact code replacement to a repository file."""

        # 1. Resolve and validate the target path.
        try:
            file_path = Path(change.file_path).resolve()

            if repo_root is not None:
                root = Path(repo_root).resolve()
                file_path.relative_to(root)

        except (OSError, RuntimeError, ValueError) as exc:
            return False, f"Rejected invalid or unsafe target path: {exc}"

        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        if not file_path.is_file():
            return False, f"Path is not a file: {file_path}"

        # 2. Validate the patch fields.
        if not change.original_code.strip():
            return False, "Original code is empty."

        if not change.new_code.strip():
            return False, "Replacement code is empty."

        if change.original_code == change.new_code:
            return False, "Original and replacement code are identical."

        # 3. Reject common standalone placeholders.
        placeholder_patterns = [
            r"(?m)^\s*\.\.\.\s*(?:#.*)?$",
            r"(?im)^\s*#\s*code\s+here\s*$",
            r"(?im)^\s*#\s*existing\s+code\s*$",
            r"(?im)^\s*#\s*rest\s+of\s+code\s*$",
            r"(?im)^\s*#\s*<existing\s+code>\s*$",
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, change.original_code):
                return False, "Original code contains a placeholder."

            if re.search(pattern, change.new_code):
                return False, "Replacement code contains a placeholder."

        # 4. Read the latest file contents.
        try:
            current_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return False, f"Could not read target file: {exc}"

        occurrences = current_code.count(change.original_code)

        if occurrences != 1:
            return False, (
                "Expected exactly one occurrence of original code, "
                f"but found {occurrences}."
            )

        modified_code = current_code.replace(
            change.original_code,
            change.new_code,
            1,
        )

        if modified_code == current_code:
            return False, "Patch produced no changes."

        # 5. Check Python syntax before writing.
        if file_path.suffix.lower() == ".py":
            try:
                ast.parse(modified_code.lstrip("\ufeff"), filename=str(file_path))
            except SyntaxError as exc:
                return False, (
                    f"Replacement produces invalid Python syntax: {exc}"
                )

        # 6. Write atomically to protect against interrupted writes.
        temporary_path = None

        try:
            original_mode = file_path.stat().st_mode

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=str(file_path.parent),
                prefix=f".{file_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(modified_code)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            temporary_path.chmod(original_mode)
            os.replace(temporary_path, file_path)
            temporary_path = None

        except OSError as exc:
            return False, f"Failed to apply patch: {exc}"

        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

        return True, "Patch applied successfully."
