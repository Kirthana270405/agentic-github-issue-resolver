from app.workflow.graph import route_after_commit, route_after_push


def test_successful_commit_allows_push():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": True,
        "git_automation_status": "committed_locally",
    }
    assert route_after_commit(state) == "push"


def test_local_automation_disabled_prevents_push():
    state = {
        "enable_local_git_automation": False,
        "enable_remote_git_automation": True,
        "git_automation_status": "committed_locally",
    }
    assert route_after_commit(state) == "finish"


def test_remote_automation_disabled_prevents_push():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": False,
        "git_automation_status": "committed_locally",
    }
    assert route_after_commit(state) == "finish"


def test_failed_commit_prevents_push():
    state = {
        "enable_local_git_automation": True,
        "enable_remote_git_automation": True,
        "git_automation_status": "failed",
    }
    assert route_after_commit(state) == "finish"


def test_successful_push_allows_pull_request_creation():
    state = {"git_push_status": "success"}
    assert route_after_push(state) == "create_pr"


def test_failed_push_prevents_pull_request_creation():
    state = {"git_push_status": "failed"}
    assert route_after_push(state) == "finish"


def test_disabled_push_prevents_pull_request_creation():
    state = {"git_push_status": "disabled"}
    assert route_after_push(state) == "finish"
