
from unittest.mock import patch

from app.workflow.git_automation import (
    create_pull_request_node,
    push_branch_node,
)


def valid_state():
    return {
        "owner": "Kirthana270405",
        "repo": "agentic-issue-resolver-test",
        "issue_number": 12,
        "issue_title": "Test issue",
        "issue_url": "https://github.com/Kirthana270405/agentic-issue-resolver-test/issues/12",
        "git_branch": "agent/issue-12",
        "git_commit": "abc123",
        "git_automation_status": "committed_locally",
        "enable_local_git_automation": True,
        "enable_remote_git_automation": True,
        "git_push_status": "success",
        "repository_test_result": {"success": True, "skipped": False},
        "final_status": "success",
        "patch_application_results": [
            {"file_path": "example.py", "applied": True}
        ],
    }


def test_push_disabled_by_default():
    state = valid_state()
    state["enable_remote_git_automation"] = False

    with patch("app.workflow.git_automation.RepositoryManager.push_branch") as push:
        result = push_branch_node(state)

    assert result["git_push_status"] == "disabled"
    push.assert_not_called()


def test_push_requires_successful_commit():
    state = valid_state()
    state["git_automation_status"] = "failed"

    with patch("app.workflow.git_automation.RepositoryManager.push_branch") as push:
        result = push_branch_node(state)

    assert result["git_push_status"] == "failed"
    push.assert_not_called()


def test_push_success():
    with patch(
        "app.workflow.git_automation.RepositoryManager.push_branch",
        return_value="agent/issue-12",
    ) as push:
        result = push_branch_node(valid_state())

    assert result["git_push_status"] == "success"
    push.assert_called_once()


def test_pull_request_requires_successful_push():
    state = valid_state()
    state["git_push_status"] = "failed"

    with patch(
        "app.workflow.git_automation.GitHubClient.create_pull_request"
    ) as create_pr:
        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "failed"
    create_pr.assert_not_called()


def test_pull_request_success():
    expected = {
        "number": 7,
        "url": "https://github.com/example/repo/pull/7",
        "state": "open",
    }

    with patch(
        "app.workflow.git_automation.GitHubClient.create_pull_request",
        return_value=expected,
    ) as create_pr:
        result = create_pull_request_node(valid_state())

    assert result["pull_request_status"] == "created"
    assert result["pull_request_number"] == 7
    assert result["pull_request_url"] == expected["url"]
    create_pr.assert_called_once()


def test_pull_request_failure_is_recorded():
    with patch(
        "app.workflow.git_automation.GitHubClient.create_pull_request",
        side_effect=RuntimeError("simulated API failure"),
    ):
        result = create_pull_request_node(valid_state())

    assert result["pull_request_status"] == "failed"
    assert "simulated API failure" in result["git_automation_error"]
