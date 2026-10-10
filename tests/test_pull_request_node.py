from unittest.mock import patch

from app.workflow.git_automation import create_pull_request_node


def valid_state():
    return {
        "enable_remote_git_automation": True,
        "git_push_status": "success",
        "owner": "test-owner",
        "repo": "test-repo",
        "git_branch": "agent/issue-123",
        "issue_number": 123,
        "issue_title": "Fix calculator",
        "issue_url": "https://github.com/test-owner/test-repo/issues/123",
        "base_branch": "main",
    }


def test_successful_response_records_pull_request():
    state = valid_state()
    response = {
        "number": 456,
        "url": "https://github.com/test-owner/test-repo/pull/456",
    }

    with patch(
        "app.workflow.git_automation.GitHubClient"
    ) as mock_client:
        mock_client.return_value.create_pull_request.return_value = response

        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "created"
    assert result["pull_request_number"] == 456
    assert result["pull_request_url"] == response["url"]
    mock_client.return_value.create_pull_request.assert_called_once_with(
        owner="test-owner",
        repo="test-repo",
        title="Fix issue #123: Fix calculator",
        body=(
            "Automated fix for issue #123.\n\n"
            "Original issue: https://github.com/test-owner/test-repo/issues/123\n\n"
            "The workflow applied and validated the patch and ran repository tests "
            "before committing this branch."
        ),
        head="test-owner:agent/issue-123",
        base="main",
    )


def test_pr_is_not_created_when_push_did_not_succeed():
    state = valid_state()
    state["git_push_status"] = "failed"

    with patch(
        "app.workflow.git_automation.GitHubClient"
    ) as mock_client:
        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "failed"
    mock_client.assert_not_called()


def test_disabled_remote_automation_skips_pr():
    state = valid_state()
    state["enable_remote_git_automation"] = False

    with patch(
        "app.workflow.git_automation.GitHubClient"
    ) as mock_client:
        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "disabled"
    mock_client.assert_not_called()


def test_github_api_error_is_reported():
    state = valid_state()

    with patch(
        "app.workflow.git_automation.GitHubClient"
    ) as mock_client:
        mock_client.return_value.create_pull_request.side_effect = (
            RuntimeError("simulated API failure")
        )

        result = create_pull_request_node(state)

    assert result["pull_request_status"] == "failed"
    assert "simulated API failure" in result["git_automation_error"]
