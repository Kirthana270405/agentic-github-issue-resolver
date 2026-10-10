
import ast
import re
from pathlib import Path

from app.agents.code_generator import GeneratedChange


class PatchValidator:
    def validate(
        self,
        change: GeneratedChange,
        repo_root: str | Path | None = None,
    ) -> tuple[bool, str]:
        """Validate a patch without modifying the repository."""

        # 1. Validate the target path.
        try:
            file_path = Path(change.file_path).resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            return False, f"Invalid target path: {exc}"

        # 2. Ensure the target remains inside the repository.
        if repo_root is not None:
            try:
                root = Path(repo_root).resolve()
                file_path.relative_to(root)
            except (OSError, RuntimeError, ValueError):
                return False, (
                    f"Target is outside the repository: {file_path}"
                )

        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        if not file_path.is_file():
            return False, f"Path is not a file: {file_path}"

        # 3. Validate patch contents.
        if not change.original_code.strip():
            return False, "Original code is empty."

        if not change.new_code.strip():
            return False, "Replacement code is empty."

        if change.original_code == change.new_code:
            return False, "Original and replacement code are identical."

        # 4. Reject common standalone placeholders.
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

        # 5. Read the current file.
        try:
            current_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return False, f"Could not read target file: {exc}"

        # 6. Require an exact, unique match.
        occurrences = current_code.count(change.original_code)

        if occurrences == 0:
            return False, "Original code was not found in the current file."

        if occurrences != 1:
            return False, (
                "Original code is ambiguous: "
                f"found {occurrences} occurrences."
            )

        # 7. Validate the resulting file before allowing application.
        modified_code = current_code.replace(
            change.original_code,
            change.new_code,
            1,
        )

        if modified_code == current_code:
            return False, "Patch would not modify the file."

        if file_path.suffix.lower() == ".py":
            try:
                ast.parse(modified_code.lstrip("\ufeff"), filename=str(file_path))
            except SyntaxError as exc:
                return False, (
                    f"Replacement produces invalid Python syntax: {exc}"
                )

        return True, "Patch is valid."
