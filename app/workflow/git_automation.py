
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from app.github.client import GitHubClient
from app.repository.manager import RepositoryManager
from app.workflow.state import WorkflowState


def prepare_local_branch_node(state: WorkflowState) -> dict:
    """Prepare an isolated local branch before applying patches."""

    if not state.get("enable_local_git_automation", False):
        return {"git_automation_status": "disabled"}

    existing_branch = state.get("git_branch", "")
    if existing_branch:
        return {"git_automation_status": "branch_ready"}

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()

    if not owner or not repo_name:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "Repository owner and name are required.",
        }

    repo_root = (Path("workspace") / f"{owner}_{repo_name}").resolve()

    if not repo_root.is_dir():
        return {
            "git_automation_status": "failed",
            "git_automation_error": f"Repository not found: {repo_root}",
        }

    issue_number = state.get("issue_number")
    branch_name = f"agent/issue-{issue_number or 'local'}"

    try:
        manager = RepositoryManager()
        manager.create_branch(repo_root, branch_name)

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
    """Commit only successfully applied patches after repository tests pass."""

    if not state.get("enable_local_git_automation", False):
        return {"git_automation_status": "disabled"}

    branch_name = state.get("git_branch", "")
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

    test_result = state.get("repository_test_result", {})
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

    repo_root = (Path("workspace") / f"{owner}_{repo_name}").resolve()

    applied_paths = [
        item.get("file_path", "")
        for item in state.get("patch_application_results", [])
        if item.get("applied", False) and item.get("file_path")
    ]
    applied_paths = list(dict.fromkeys(applied_paths))

    if not applied_paths:
        return {
            "git_automation_status": "failed",
            "git_automation_error": "No successfully applied patch files found.",
        }

    try:
        from git import Repo

        git_repo = Repo(repo_root)
        try:
            if git_repo.head.is_detached:
                raise ValueError("Repository is in detached HEAD state.")

            if git_repo.active_branch.name != branch_name:
                raise ValueError(
                    "The active branch does not match the prepared branch."
                )
        finally:
            git_repo.close()

        commit_hash = RepositoryManager().commit_changes(
            repo_dir=repo_root,
            message=f"Fix issue #{state.get('issue_number', 'local')}",
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
    """Push a successfully committed branch only when remote automation is enabled."""

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
            "git_automation_error": "A successful local commit is required before push.",
        }

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()
    branch_name = str(state.get("git_branch", "")).strip()

    if not owner or not repo_name or not branch_name:
        return {
            "git_push_status": "failed",
            "git_automation_error": "Repository owner, name, and branch are required.",
        }

    repo_root = (Path("workspace") / f"{owner}_{repo_name}").resolve()

    try:
        pushed_branch = RepositoryManager().push_branch(repo_root)

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
    """Create a pull request only after the branch push succeeds."""

    if not state.get("enable_remote_git_automation", False):
        return {"pull_request_status": "disabled"}

    if state.get("git_push_status") != "success":
        return {
            "pull_request_status": "failed",
            "git_automation_error": "Cannot create a PR because branch push failed.",
        }

    owner = str(state.get("owner", "")).strip()
    repo_name = str(state.get("repo", "")).strip()
    branch_name = str(state.get("git_branch", "")).strip()

    if not owner or not repo_name or not branch_name:
        return {
            "pull_request_status": "failed",
            "git_automation_error": "Repository owner, name, and branch are required.",
        }

    issue_number = state.get("issue_number", "local")
    issue_title = str(state.get("issue_title", "")).strip()
    issue_url = str(state.get("issue_url", "")).strip()
    base_branch = str(state.get("base_branch", "main")).strip() or "main"

    title = f"Fix issue #{issue_number}: {issue_title}".strip()
    if not issue_title:
        title = f"Fix issue #{issue_number}"

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

        print(f"[GitHub] Pull request created: {result['url']}")

        return {
            "pull_request_status": "created",
            "pull_request_number": result["number"],
            "pull_request_url": result["url"],
            "git_automation_error": "",
        }

    except Exception as exc:
        # The commit and push may already have succeeded. Preserve those results.
        message = f"Pull-request creation failed: {exc}"
        print(f"[GitHub] {message}")
        return {
            "pull_request_status": "failed",
            "git_automation_error": message,
        }
