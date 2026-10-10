from pathlib import Path
from typing import List


class FileDiscovery:

    ALLOWED_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".cpp",
        ".c",
        ".h",
    }

    IGNORED_DIRECTORIES = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".pytest_cache",
    }

    def discover(self, repo_path: Path) -> List[Path]:

        files = []

        for path in repo_path.rglob("*"):

            if not path.is_file():
                continue

            if any(
                part in self.IGNORED_DIRECTORIES
                for part in path.parts
            ):
                continue

            if path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
                continue

            files.append(path)

        return files