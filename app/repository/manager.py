
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

        if not isinstance(branch_name, str) or not branch_name.strip():
            raise ValueError("Branch name cannot be empty.")

        if branch_name.startswith("-"):
            raise ValueError("Invalid branch name.")

        try:
            repo.git.check_ref_format("--branch", branch_name)
        except GitCommandError as exc:
            raise ValueError(f"Invalid branch name: {branch_name}") from exc

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
        """Commit only explicitly listed files, rejecting pre-staged changes."""
        repo = Repo(repo_dir)
        root = Path(repo.working_tree_dir).resolve()

        if not isinstance(message, str) or not message.strip():
            raise ValueError("Commit message cannot be empty.")

        if not file_paths:
            raise ValueError("No files were specified for the commit.")

        if repo.head.is_detached:
            raise ValueError("Cannot commit from a detached HEAD.")

        # Never include unrelated changes that were staged beforehand.
        if repo.index.diff("HEAD"):
            raise ValueError(
                "The Git index already contains staged changes. "
                "Unstage or commit them before running automated commits."
            )

        safe_paths = []

        for file_path in file_paths:
            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError("Every file path must be a non-empty string.")

            supplied_path = Path(file_path)
            candidate = (
                supplied_path if supplied_path.is_absolute()
                else root / supplied_path
            ).resolve()

            try:
                relative_path = candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"File is outside the repository: {file_path}"
                ) from exc

            if not candidate.is_file():
                raise ValueError(f"File does not exist: {file_path}")

            relative_name = relative_path.as_posix()
            if relative_name not in safe_paths:
                safe_paths.append(relative_name)

        if not safe_paths:
            raise ValueError("No valid files were specified for the commit.")

        # Stage only the validated files.
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
        """Push the currently checked-out branch to the configured remote."""
        repo = Repo(repo_dir)

        if repo.head.is_detached:
            raise ValueError("Cannot push from a detached HEAD.")

        if repo.is_dirty(untracked_files=True):
            raise ValueError(
                "Cannot push while the working tree contains uncommitted changes."
            )

        branch_name = repo.active_branch.name

        if not branch_name:
            raise ValueError("No active branch is available to push.")

        if remote_name not in [remote.name for remote in repo.remotes]:
            raise ValueError(f"Git remote not found: {remote_name}")

        remote = repo.remote(remote_name)

        remote.push(
            refspec=f"{branch_name}:{branch_name}",
            set_upstream=True,
        )

        return branch_name
