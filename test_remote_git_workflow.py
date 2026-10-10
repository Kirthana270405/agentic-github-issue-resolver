
from unittest.mock import patch

import app.workflow.graph as workflow


def test_successful_commit_routes_to_push_when_remote_enabled():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": True,
        "git_automation_status": "committed_locally",
    }

    assert workflow.route_after_commit(state) == "push"


def test_successful_commit_does_not_push_when_remote_disabled():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": False,
        "git_automation_status": "committed_locally",
    }

    assert workflow.route_after_commit(state) == "finish"


def test_failed_commit_never_routes_to_push():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": True,
        "git_automation_status": "failed",
    }

    assert workflow.route_after_commit(state) == "finish"


def test_remote_enabled_without_local_automation_does_not_push():
    state = {
        "enable_local_git_automation": False,
        "enable_remote_git_automation": True,
        "git_automation_status": "committed_locally",
    }

    assert workflow.route_after_commit(state) == "finish"


def test_failed_push_prevents_pull_request_creation():
    from app.workflow.git_automation import create_pull_request_node

    state = {
        "enable_remote_git_automation": True,
        "git_push_status": "failed",
        "owner": "testowner",
        "repo": "testrepo",
        "git_branch": "agent/issue-1",
    }

    with patch(
        "app.workflow.git_automation.GitHubClient.create_pull_request"
    ) as create_pr:
        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "failed"
    create_pr.assert_not_called()


def test_disabled_remote_automation_does_not_create_pull_request():
    from app.workflow.git_automation import create_pull_request_node

    state = {
        "enable_remote_git_automation": False,
        "git_push_status": "success",
        "owner": "testowner",
        "repo": "testrepo",
        "git_branch": "agent/issue-1",
    }

    with patch(
        "app.workflow.git_automation.GitHubClient.create_pull_request"
    ) as create_pr:
        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "disabled"
    create_pr.assert_not_called()
