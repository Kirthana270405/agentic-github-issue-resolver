
import sys

import requests

from app.workflow.graph import build_graph


GITHUB_API = "https://api.github.com"


def fetch_issue(owner: str, repo: str, issue_number: int) -> dict:
    """Fetch a real issue from the GitHub API."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}"

    response = requests.get(
        url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=20,
    )
    response.raise_for_status()

    issue = response.json()

    # GitHub pull requests also appear in the issues endpoint.
    if "pull_request" in issue:
        raise ValueError(
            f"#{issue_number} is a pull request, not a regular issue."
        )

    return issue


def main() -> None:
    owner = "psf"
    repo = "requests"
    issue_number = 1

    print("=" * 60)
    print("GITHUB ISSUE RESOLVER")
    print("=" * 60)

    try:
        issue = fetch_issue(owner, repo, issue_number)
    except requests.RequestException as exc:
        print(f"[Error] Could not fetch GitHub issue: {exc}")
        sys.exit(1)
    except (ValueError, KeyError) as exc:
        print(f"[Error] Invalid issue response: {exc}")
        sys.exit(1)

    issue_title = issue.get("title") or ""
    issue_body = issue.get("body") or ""

    print(f"\nRepository: {owner}/{repo}")
    print(f"Issue: #{issue_number}")
    print(f"Title: {issue_title}")
    print(f"State: {issue.get('state', 'unknown')}")
    print(f"Description length: {len(issue_body)} characters")

    if not issue_title.strip() and not issue_body.strip():
        print("[Error] The issue has no title or description.")
        sys.exit(1)

    initial_state = {
        "owner": owner,
        "repo": repo,
        "issue_number": issue_number,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "issue_url": issue.get(
            "html_url",
            f"https://github.com/{owner}/{repo}/issues/{issue_number}",
        ),
        "problem": "",
        "expected_behavior": "",
        "likely_components": [],
        "technical_constraints": [],
        "acceptance_criteria": [],
        "relevant_code": [],
        "implementation_plan": {},
        "generated_patches": [],
        "patch_validation_results": [],
        "patch_application_results": [],
        "test_results": [],
        "repository_test_result": {},
        "debug_analysis": {},
        "retry_count": 0,
        "final_status": "",
        "error": "",
    }

    print("\n[Workflow] Building graph...")

    try:
        graph = build_graph()

        print("[Workflow] Running issue resolver...\n")
        final_state = graph.invoke(initial_state)

    except KeyboardInterrupt:
        print("\n[Workflow] Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n[Workflow Error] {type(exc).__name__}: {exc}")
        raise

    print("\n" + "=" * 60)
    print("WORKFLOW SUMMARY")
    print("=" * 60)

    print(f"Issue: {initial_state['issue_url']}")
    print(f"Final status: {final_state.get('final_status', 'unknown')}")
    print(f"Retry count: {final_state.get('retry_count', 0)}")

    plan = final_state.get("implementation_plan", {})
    print(f"Plan: {plan.get('summary', 'No plan available')}")

    patches = final_state.get("generated_patches", [])
    print(f"Generated patches: {len(patches)}")

    for patch in patches:
        print(f"  - {patch.get('file_path', 'Unknown file')}")
        print(f"    Explanation: {patch.get('explanation', 'Not provided')}")

    applications = final_state.get("patch_application_results", [])
    applied_count = sum(
        1 for item in applications if item.get("applied", False)
    )
    print(f"Successfully applied patches: {applied_count}")

    test_result = final_state.get("repository_test_result", {})

    if test_result:
        if test_result.get("skipped"):
            print("Repository tests: SKIPPED")
            print(test_result.get("stderr", "No reason provided."))
        elif test_result.get("success"):
            print("Repository tests: PASSED")
        else:
            print(
                "Repository tests: FAILED "
                f"(exit code: {test_result.get('exit_code')})"
            )
            if test_result.get("stdout"):
                print("\nTest output:")
                print(test_result["stdout"][-5000:])
            if test_result.get("stderr"):
                print("\nTest errors:")
                print(test_result["stderr"][-2000:])
    else:
        print("Repository tests: Not executed")

    print("\n" + "=" * 60)
    print("Workflow finished.")
    print("=" * 60)


if __name__ == "__main__":
    main()
