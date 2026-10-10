
from pathlib import Path

from git import (
    GitCommandError,
    InvalidGitRepositoryError,
    NoSuchPathError,
    Repo,
)

from app.github.client import GitHubClient
from app.repository.manager import RepositoryManager
from app.workflow.state import WorkflowState


def _get_repo_root(owner: str, repo_name: str) -> Path:
    """Return the expected local repository path."""
    return (Path("workspace") / f"{owner}_{repo_name}").resolve()


def _validate_active_branch(repo_root: Path, expected_branch: str) -> None:
    """Ensure the expected branch exists and is currently checked out."""
    if not repo_root.is_dir():
        raise ValueError(f"Repository not found: {repo_root}")

    git_repo = Repo(repo_root)
    try:
        if git_repo.head.is_detached:
            raise ValueError("Repository is in detached HEAD state.")

        local_branches = {branch.name for branch in git_repo.branches}

        if expected_branch not in local_branches:
            raise ValueError(
                f"Prepared branch does not exist locally: {expected_branch}"
            )

        active_branch = git_repo.active_branch.name
        if active_branch != expected_branch:
            raise ValueError(
                f"Expected branch '{expected_branch}', "
                f"but active branch is '{active_branch}'."
            )
    finally:
        git_repo.close()


def prepare_local_branch_node(state: WorkflowState) -> dict:
    """Prepare or safely reuse a local branch before applying patches."""

    if not state.get("enable_local_git_automation", False):
        return {"git_automation_status": "disabled"}

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()

    if not owner or not repo_name:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Repository owner and name are required.",
        }

    repo_root = _get_repo_root(owner, repo_name)

    if not repo_root.is_dir():
        return {
            "git_automation_status": "failed",
            "git_automation_error": f"Repository not found: {repo_root}",
        }

    existing_branch = str(state.get("git_branch", "")).strip()

    if existing_branch:
        try:
            _validate_active_branch(repo_root, existing_branch)
            return {
                "git_automation_status": "branch_ready",
                "git_automation_error": "",
            }
        except (
            ValueError,
            GitCommandError,
            InvalidGitRepositoryError,
            NoSuchPathError,
            OSError,
        ) as exc:
            message = f"Could not reuse prepared branch: {exc}"
            print(f"[Git] {message}")
            return {
                "git_automation_status": "failed",
                "git_automation_error": message,
            }

    issue_number = state.get("issue_number")
    branch_name = f"agent/issue-{issue_number or 'local'}"

    try:
        RepositoryManager().create_branch(repo_root, branch_name)
        _validate_active_branch(repo_root, branch_name)

        print(f"[Git] Local branch prepared: {branch_name}")

        return {
            "git_branch": branch_name,
            "git_automation_status": "branch_ready",
            "git_automation_error": "",
        }

    except (
        ValueError,
        GitCommandError,
        InvalidGitRepositoryError,
        NoSuchPathError,
        OSError,
    ) as exc:
        message = f"Could not prepare local branch: {exc}"
        print(f"[Git] {message}")
        return {
            "git_automation_status": "failed",
            "git_automation_error": message,
        }


def commit_local_changes_node(state: WorkflowState) -> dict:
    """Commit successfully applied patches after repository tests pass."""

    if not state.get("enable_local_git_automation", False):
        return {"git_automation_status": "disabled"}

    branch_name = str(state.get("git_branch", "")).strip()

    if not branch_name:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "No prepared Git branch is available.",
        }

    if state.get("final_status") != "success":
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Final patch validation did not pass.",
        }

    test_result = state.get("repository_test_result")

    if not isinstance(test_result, dict):
        return {
            "git_automation_status": "failed",
            "git_automation_error": (
                "Repository test results are missing or invalid."
            ),
        }

    if test_result.get("skipped") or not test_result.get("success"):
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Repository tests did not pass.",
        }

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()

    if not owner or not repo_name:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Repository owner and name are required.",
        }

    repo_root = _get_repo_root(owner, repo_name)
    application_results = state.get("patch_application_results", [])

    if not isinstance(application_results, list):
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Patch application results are invalid.",
        }

    applied_paths = list(
        dict.fromkeys(
            item["file_path"]
            for item in application_results
            if isinstance(item, dict)
            and item.get("applied") is True
            and isinstance(item.get("file_path"), str)
            and item["file_path"].strip()
        )
    )

    if not applied_paths:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "No successfully applied patch files found.",
        }

    try:
        _validate_active_branch(repo_root, branch_name)

        commit_hash = RepositoryManager().commit_changes(
            repo_dir=repo_root,
            message=f"Fix issue #{state.get('issue_number') or 'local'}",
            file_paths=applied_paths,
        )

        print(f"[Git] Local commit created: {commit_hash[:12]}")

        return {
            "git_commit": commit_hash,
            "git_automation_status": "committed_locally",
            "git_automation_error": "",
        }

    except (
        ValueError,
        GitCommandError,
        InvalidGitRepositoryError,
        NoSuchPathError,
        OSError,
    ) as exc:
        message = f"Local commit failed: {exc}"
        print(f"[Git] {message}")
        return {
            "git_automation_status": "failed",
            "git_automation_error": message,
        }


def push_branch_node(state: WorkflowState) -> dict:
    """Push only the intended, successfully committed branch."""

    if not state.get("enable_remote_git_automation", False):
        return {"git_push_status": "disabled"}

    if not state.get("enable_local_git_automation", False):
        return {
            "git_push_status": "failed",
            "git_automation_error": (
                "Remote automation requires local Git automation to be enabled."
            ),
        }

    if state.get("git_automation_status") != "committed_locally":
        return {
            "git_push_status": "failed",
            "git_automation_error": (
                "A successful local commit is required before push."
            ),
        }

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()
    branch_name = str(state.get("git_branch", "")).strip()

    if not owner or not repo_name or not branch_name:
        return {
            "git_push_status": "failed",
            "git_automation_error": (
                "Repository owner, name, and branch are required."
            ),
        }

    repo_root = _get_repo_root(owner, repo_name)

    try:
        _validate_active_branch(repo_root, branch_name)

        pushed_branch = RepositoryManager().push_branch(repo_root)

        if pushed_branch != branch_name:
            raise ValueError(
                f"Push returned branch '{pushed_branch}', "
                f"but '{branch_name}' was expected."
            )

        print(f"[Git] Branch pushed: {pushed_branch}")

        return {
            "git_push_status": "success",
            "git_automation_error": "",
        }

    except (
        ValueError,
        GitCommandError,
        InvalidGitRepositoryError,
        NoSuchPathError,
        OSError,
    ) as exc:
        message = f"Branch push failed: {exc}"
        print(f"[Git] {message}")
        return {
            "git_push_status": "failed",
            "git_automation_error": message,
        }


def create_pull_request_node(state: WorkflowState) -> dict:
    """Create a pull request only after a successful branch push."""

    if not state.get("enable_remote_git_automation", False):
        return {"pull_request_status": "disabled"}

    if state.get("git_push_status") != "success":
        return {
            "pull_request_status": "failed",
            "git_automation_error": (
                "Cannot create a PR because branch push failed."
            ),
        }

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()
    branch_name = str(state.get("git_branch", "")).strip()

    if not owner or not repo_name or not branch_name:
        return {
            "pull_request_status": "failed",
            "git_automation_error": (
                "Repository owner, name, and branch are required."
            ),
        }

    issue_number = state.get("issue_number") or "local"
    issue_title = str(state.get("issue_title", "")).strip()
    issue_url = str(state.get("issue_url", "")).strip()
    base_branch = str(state.get("base_branch", "main")).strip() or "main"

    title = (
        f"Fix issue #{issue_number}: {issue_title}"
        if issue_title
        else f"Fix issue #{issue_number}"
    )

    body = (
        f"Automated fix for issue #{issue_number}.\n\n"
        f"Original issue: {issue_url or 'Not provided'}\n\n"
        "The workflow applied and validated the patch and ran repository tests "
        "before committing this branch."
    )

    try:
        result = GitHubClient().create_pull_request(
            owner=owner,
            repo=repo_name,
            title=title,
            body=body,
            head=f"{owner}:{branch_name}",
            base=base_branch,
        )

        if not isinstance(result, dict):
            raise ValueError("GitHub returned an invalid pull-request response.")

        pr_url = result.get("url")
        pr_number = result.get("number")

        if not pr_url or pr_number is None:
            raise ValueError(
                "GitHub response did not include the pull-request URL and number."
            )

        print(f"[GitHub] Pull request created: {pr_url}")

        return {
            "pull_request_status": "created",
            "pull_request_number": pr_number,
            "pull_request_url": pr_url,
            "git_automation_error": "",
        }

    except Exception as exc:
        message = f"Pull-request creation failed: {exc}"
        print(f"[GitHub] {message}")
        return {
            "pull_request_status": "failed",
            "git_automation_error": message,
        }
