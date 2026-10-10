
from pathlib import Path

from git import Repo

import app.workflow.graph as workflow


def test_graph_prepares_branch_runs_tests_and_commits_locally(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    # Create an isolated local repository with one committed file.
    repo_root = Path("workspace") / "testowner_testrepo"
    repo_root.mkdir(parents=True)

    repo = Repo.init(repo_root)

    with repo.config_writer() as config:
        config.set_value("user", "name", "Workflow Integration Test")
        config.set_value("user", "email", "workflow-test@example.com")

    source_file = repo_root / "sample.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    repo.index.add(["sample.py"])
    repo.index.commit("Initial commit")
    repo.close()

    # Stub expensive AI stages while keeping the actual Git nodes
    # and graph routing.
    monkeypatch.setattr(
        workflow,
        "analyze_issue_node",
        lambda state: {
            "problem": "Update VALUE",
            "expected_behavior": "VALUE should equal 2",
        },
    )

    monkeypatch.setattr(
        workflow,
        "retrieve_code_node",
        lambda state: {
            "relevant_code": [
                {
                    "file_path": "sample.py",
                    "content": "VALUE = 1\n",
                }
            ]
        },
    )

    monkeypatch.setattr(
        workflow,
        "planning_node",
        lambda state: {
            "implementation_plan": {
                "summary": "Update VALUE to 2",
                "decision": "CHANGE_REQUIRED",
                "files_to_modify": [
                    {
                        "file_path": "sample.py",
                        "change": "Change VALUE from 1 to 2",
                        "reason": "Required by the issue",
                    }
                ],
            }
        },
    )

    monkeypatch.setattr(
        workflow,
        "code_generation_node",
        lambda state: {
            "generated_patches": [{"file_path": "sample.py"}]
        },
    )

    monkeypatch.setattr(
        workflow,
        "patch_validation_node",
        lambda state: {
            "patch_validation_results": [{"valid": True}]
        },
    )

    def apply_patch(state):
        source_file.write_text("VALUE = 2\n", encoding="utf-8")
        return {
            "patch_application_results": [
                {
                    "file_path": str(source_file.resolve()),
                    "applied": True,
                }
            ]
        }

    monkeypatch.setattr(workflow, "patch_application_node", apply_patch)

    monkeypatch.setattr(
        workflow,
        "final_validation_node",
        lambda state: {
            "final_status": "success",
            "final_validation_errors": [],
        },
    )

    monkeypatch.setattr(
        workflow,
        "test_execution_node",
        lambda state: {
            "repository_test_result": {
                "success": True,
                "skipped": False,
                "exit_code": 0,
            }
        },
    )

    result = workflow.build_graph().invoke(
        {
            "owner": "testowner",
            "repo": "testrepo",
            "issue_number": 42,
            "issue_title": "Update VALUE",
            "issue_body": "Change VALUE to 2",
            "retry_count": 0,
            "enable_local_git_automation": True,
        }
    )

    # Confirm that branch preparation and local commit succeeded.
    assert result["git_branch"] == "agent/issue-42"
    assert result["git_automation_status"] == "committed_locally"
    assert result["git_commit"]

    check = Repo(repo_root)
    try:
        assert check.active_branch.name == "agent/issue-42"
        assert check.head.commit.hexsha == result["git_commit"]
        assert "sample.py" in check.head.commit.stats.files
        assert source_file.read_text(encoding="utf-8") == "VALUE = 2\n"
        assert list(check.remotes) == []
    finally:
        check.close()
