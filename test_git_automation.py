
from pathlib import Path

from git import Repo

from app.workflow.git_automation import (
    prepare_local_branch_node,
    commit_local_changes_node,
)


def test_local_branch_and_selective_commit(tmp_path, monkeypatch):
    # Use an isolated temporary repository, never the real workspace.
    monkeypatch.chdir(tmp_path)

    repo_root = Path("workspace") / "testowner_testrepo"
    repo_root.mkdir(parents=True)

    repo = Repo.init(repo_root)

    with repo.config_writer() as config:
        config.set_value("user", "name", "Day 6 Test")
        config.set_value("user", "email", "day6-test@example.com")

    target = repo_root / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")

    unrelated = repo_root / "notes.txt"
    unrelated.write_text("original note\n", encoding="utf-8")

    repo.index.add(["sample.py", "notes.txt"])
    repo.index.commit("Initial commit")
    repo.close()

    # Prepare the local branch.
    branch_result = prepare_local_branch_node({
        "owner": "testowner",
        "repo": "testrepo",
        "issue_number": 42,
        "enable_local_git_automation": True,
    })

    assert branch_result["git_automation_status"] == "branch_ready"
    assert branch_result["git_branch"] == "agent/issue-42"

    # Simulate one applied patch and an unrelated change.
    target.write_text("value = 2\n", encoding="utf-8")
    unrelated.write_text("unrelated change\n", encoding="utf-8")

    state = {
        "owner": "testowner",
        "repo": "testrepo",
        "issue_number": 42,
        "enable_local_git_automation": True,
        "git_branch": branch_result["git_branch"],
        "final_status": "success",
        "repository_test_result": {
            "success": True,
            "skipped": False,
        },
        "patch_application_results": [
            {
                "file_path": str(target.resolve()),
                "applied": True,
            }
        ],
    }

    commit_result = commit_local_changes_node(state)

    assert commit_result["git_automation_status"] == "committed_locally"
    assert commit_result["git_commit"]

    check = Repo(repo_root)
    try:
        assert check.active_branch.name == "agent/issue-42"
        assert check.head.commit.hexsha == commit_result["git_commit"]
        assert set(check.head.commit.stats.files) == {"sample.py"}
        assert "notes.txt" in check.git.diff("HEAD", name_only=True).splitlines()
        assert check.remotes == []
    finally:
        check.close()
