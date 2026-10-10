
from langgraph.graph import END, START, StateGraph

from app.workflow.state import WorkflowState
from app.workflow.nodes import (
    analyze_issue_node,
    retrieve_code_node,
    planning_node,
    code_generation_node,
    patch_validation_node,
    patch_application_node,
    final_validation_node,
    test_execution_node,
    debugging_node,
    prepare_retry_node,
)
from app.workflow.git_automation import (
    prepare_local_branch_node,
    commit_local_changes_node,
    push_branch_node,
    create_pull_request_node,
)


MAX_RETRIES = 2


def route_after_planning(state: WorkflowState) -> str:
    """Generate code only when the plan explicitly requires a change."""
    plan = state.get("implementation_plan") or {}

    if not isinstance(plan, dict):
        print("\n[Graph] Invalid implementation plan; stopping safely.")
        return "finish"

    decision = plan.get("decision")
    changes = plan.get("files_to_modify") or []

    if not isinstance(changes, list):
        print("\n[Graph] Invalid file-change list; stopping safely.")
        return "finish"

    if decision == "ALREADY_SUPPORTED":
        print(
            "\n[Graph] Existing implementation appears to support "
            "the requested behavior. No patch will be generated."
        )
        return "finish"

    if decision == "INSUFFICIENT_CONTEXT":
        print(
            "\n[Graph] Insufficient evidence for a safe code change. "
            "Stopping without modifying the repository."
        )
        return "finish"

    if decision != "CHANGE_REQUIRED":
        print(
            "\n[Graph] Missing or invalid planner decision; "
            "stopping safely."
        )
        return "finish"

    if not changes:
        print(
            "\n[Graph] A change was requested, but no files were proposed. "
            "Stopping safely."
        )
        return "finish"

    for change in changes:
        if not isinstance(change, dict):
            print("\n[Graph] Malformed file-change entry; stopping safely.")
            return "finish"

        if not all(
            isinstance(change.get(field), str)
            and change[field].strip()
            for field in ("file_path", "change", "reason")
        ):
            print(
                "\n[Graph] Incomplete file-change entry; "
                "stopping safely."
            )
            return "finish"

    print(
        f"\n[Graph] Concrete change proposed for {len(changes)} file(s)."
    )
    return "generate"


def route_after_validation(state: WorkflowState) -> str:
    """Run tests only after a patch has been applied and validated."""
    if state.get("final_status") != "success":
        print("\n[Graph] Patch validation did not pass; stopping.")
        return "finish"

    application_results = state.get("patch_application_results", [])

    if not any(
        item.get("applied", False)
        for item in application_results
    ):
        print("\n[Graph] No patch was applied; stopping.")
        return "finish"

    return "run_tests"


def route_after_tests(state: WorkflowState) -> str:
    """Retry failed tests or commit after successful tests."""
    result = state.get("repository_test_result", {})

    if result.get("skipped"):
        print("\n[Graph] Tests were skipped; stopping.")
        return "finish"

    if result.get("success"):
        print("\n[Graph] Repository tests passed.")

        if (
            state.get("enable_local_git_automation", False)
            and state.get("git_branch")
        ):
            return "commit_locally"

        return "finish"

    retries = state.get("retry_count", 0)

    if retries >= MAX_RETRIES:
        print("\n[Graph] Maximum retries reached.")
        return "finish"

    print(
        f"\n[Graph] Tests failed. "
        f"Retry allowance: {MAX_RETRIES - retries}"
    )
    return "debug"


def route_after_debug(state: WorkflowState) -> str:
    """Retry only if the debugger recommends a code-related fix."""
    diagnosis = state.get("debug_analysis", {})
    retries = state.get("retry_count", 0)

    if retries >= MAX_RETRIES:
        print("\n[Graph] Maximum retries reached.")
        return "finish"

    if not isinstance(diagnosis, dict):
        return "finish"

    if (
        diagnosis.get("category") != "code"
        or not diagnosis.get("retry_recommended", False)
    ):
        print("\n[Graph] No safe code retry recommended.")
        return "finish"

    return "prepare_retry"


def route_after_branch_preparation(state: WorkflowState) -> str:
    """Stop before patch application if requested branch preparation fails."""
    if not state.get("enable_local_git_automation", False):
        return "apply"

    if state.get("git_automation_status") == "branch_ready":
        return "apply"

    print("[Graph] Branch preparation failed; patches will not be applied.")
    return "finish"


def route_after_commit(state: WorkflowState) -> str:
    """Push only after a successful commit and explicit remote opt-in."""
    if (
        state.get("enable_local_git_automation", False)
        and state.get("enable_remote_git_automation", False)
        and state.get("git_automation_status") == "committed_locally"
    ):
        return "push"

    return "finish"


def route_after_push(state: WorkflowState) -> str:
    """Create a PR only when the push node reports success."""
    if state.get("git_push_status") == "success":
        return "create_pr"

    print("[Graph] Push failed; skipping pull-request creation.")
    return "finish"


def build_graph():
    graph = StateGraph(WorkflowState)

    # Register workflow nodes.
    graph.add_node("analyze_issue", analyze_issue_node)
    graph.add_node("retrieve_code", retrieve_code_node)
    graph.add_node("create_plan", planning_node)
    graph.add_node("generate_code", code_generation_node)
    graph.add_node("validate_patches", patch_validation_node)
    graph.add_node("prepare_local_branch", prepare_local_branch_node)
    graph.add_node("apply_patches", patch_application_node)
    graph.add_node("final_validation", final_validation_node)
    graph.add_node("run_repository_tests", test_execution_node)
    graph.add_node("debug", debugging_node)
    graph.add_node("prepare_retry", prepare_retry_node)
    graph.add_node("commit_local_changes", commit_local_changes_node)
    graph.add_node("push_branch", push_branch_node)
    graph.add_node("create_pull_request", create_pull_request_node)

    # Analyze the issue and retrieve relevant code.
    graph.add_edge(START, "analyze_issue")
    graph.add_edge("analyze_issue", "retrieve_code")
    graph.add_edge("retrieve_code", "create_plan")

    # Require an explicit, actionable planner decision.
    graph.add_conditional_edges(
        "create_plan",
        route_after_planning,
        {
            "generate": "generate_code",
            "finish": END,
        },
    )

    # Generate and validate patches.
    graph.add_edge("generate_code", "validate_patches")
    graph.add_edge("validate_patches", "prepare_local_branch")

    # Prepare a branch before applying changes when Git automation is enabled.
    graph.add_conditional_edges(
        "prepare_local_branch",
        route_after_branch_preparation,
        {
            "apply": "apply_patches",
            "finish": END,
        },
    )

    # Apply patches and perform final validation.
    graph.add_edge("apply_patches", "final_validation")

    graph.add_conditional_edges(
        "final_validation",
        route_after_validation,
        {
            "run_tests": "run_repository_tests",
            "finish": END,
        },
    )

    # Run tests, debug failures, or proceed to a local commit.
    graph.add_conditional_edges(
        "run_repository_tests",
        route_after_tests,
        {
            "debug": "debug",
            "commit_locally": "commit_local_changes",
            "finish": END,
        },
    )

    # Retry only when a code-related retry is recommended.
    graph.add_conditional_edges(
        "debug",
        route_after_debug,
        {
            "prepare_retry": "prepare_retry",
            "finish": END,
        },
    )

    graph.add_edge("prepare_retry", "retrieve_code")

    # Push only after the commit node confirms success.
    graph.add_conditional_edges(
        "commit_local_changes",
        route_after_commit,
        {
            "push": "push_branch",
            "finish": END,
        },
    )

    # Match the push node's actual git_push_status field.
    graph.add_conditional_edges(
        "push_branch",
        route_after_push,
        {
            "create_pr": "create_pull_request",
            "finish": END,
        },
    )

    graph.add_edge("create_pull_request", END)

    return graph.compile()
