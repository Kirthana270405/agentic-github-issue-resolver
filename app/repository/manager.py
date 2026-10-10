
from pathlib import Path

from git import Repo, GitCommandError


class RepositoryManager:
    def __init__(self, base_dir: str = "workspace"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def clone_repository(self, owner: str, repo: str) -> Path:
        repo_dir = self.base_dir / f"{owner}_{repo}"

        if repo_dir.exists():
            if (repo_dir / ".git").exists():
                return repo_dir
            raise ValueError(
                f"Directory exists but is not a Git repository: {repo_dir}"
            )

        repository_url = f"https://github.com/{owner}/{repo}.git"
        print(f"Cloning {owner}/{repo}...")

        Repo.clone_from(repository_url, repo_dir)

        print(f"Repository cloned to: {repo_dir}")
        return repo_dir

    def create_branch(
        self,
        repo_dir: str | Path,
        branch_name: str,
    ) -> str:
        repo = Repo(repo_dir)

        if repo.is_dirty(untracked_files=True):
            raise ValueError(
                "Working tree has changes. Commit or safely preserve them "
                "before creating a branch."
            )

        if not branch_name or branch_name.startswith("-"):
            raise ValueError("Invalid branch name.")

        if branch_name in [branch.name for branch in repo.branches]:
            raise ValueError(f"Local branch already exists: {branch_name}")

        repo.git.checkout("-b", branch_name)
        return branch_name

    def commit_changes(
        self,
        repo_dir: str | Path,
        message: str,
        file_paths: list[str],
    ) -> str:
        """Commit only the explicitly listed repository-relative files."""
        repo = Repo(repo_dir)
        root = Path(repo.working_tree_dir).resolve()

        if not message.strip():
            raise ValueError("Commit message cannot be empty.")

        if not file_paths:
            raise ValueError("No files were specified for the commit.")

        safe_paths = []

        for file_path in file_paths:
            candidate = (root / file_path).resolve()

            try:
                relative_path = candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"File is outside the repository: {file_path}"
                ) from exc

            if not candidate.is_file():
                raise ValueError(f"File does not exist: {file_path}")

            safe_paths.append(relative_path.as_posix())

        repo.index.add(safe_paths)

        if not repo.index.diff("HEAD"):
            raise ValueError(
                "No tracked changes to commit in the specified files."
            )

        commit = repo.index.commit(message)
        return commit.hexsha

    def push_branch(
        self,
        repo_dir: str | Path,
        remote_name: str = "origin",
    ) -> str:
        repo = Repo(repo_dir)

        if repo.head.is_detached:
            raise ValueError("Cannot push from a detached HEAD.")

        branch_name = repo.active_branch.name
        remote = repo.remote(remote_name)

        remote.push(
            refspec=f"{branch_name}:{branch_name}",
            set_upstream=True,
        )

        return branch_name
