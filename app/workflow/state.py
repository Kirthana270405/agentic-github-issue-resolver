from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    # Repository and issue details
    owner: str
    repo: str
    issue_number: int
    issue_title: str
    issue_body: str
    issue_url: str
    base_branch: str

    # Issue analysis
    problem: str
    expected_behavior: str
    likely_components: list[str]
    technical_constraints: list[str]
    acceptance_criteria: list[str]

    # Retrieved repository context
    relevant_code: list[dict[str, Any]]

    # Implementation planning
    # Expected decision values:
    # CHANGE_REQUIRED, ALREADY_SUPPORTED, INSUFFICIENT_CONTEXT
    implementation_plan: dict[str, Any]

    # Patch generation and validation
    generated_patches: list[dict[str, Any]]
    patch_validation_results: list[dict[str, Any]]
    patch_application_results: list[dict[str, Any]]

    # Final validation
    final_status: str
    final_validation_errors: list[str]

    # Repository test execution
    test_results: list[dict[str, Any]]
    repository_test_result: dict[str, Any]

    # Debugging and retry control
    debug_analysis: dict[str, Any]
    retry_count: int

    # Local Git automation
    enable_local_git_automation: bool
    git_branch: str
    git_commit: str
    git_automation_status: str
    git_automation_error: str

    # Remote GitHub automation
    enable_remote_git_automation: bool
    git_push_status: str
    pull_request_status: str
    pull_request_number: int
    pull_request_url: str

    # Optional workflow messages
    error: str
    messages: list[str]