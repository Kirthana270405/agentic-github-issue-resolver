
import json
import time
import sys
from pathlib import Path

import requests
from git import Repo

from app.workflow.graph import build_graph


GITHUB_API = "https://api.github.com"
OWNER = "psf"
REPO = "requests"
ISSUE_NUMBERS = [2]

# Change this to v4, v5, etc. for each fresh evaluation.
EVALUATION_VERSION = "v4"

PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE = PROJECT_ROOT / "workspace"
REPORT_PATH = PROJECT_ROOT / "issue_evaluation_results.json"


def fetch_issue(owner: str, repo: str, number: int) -> dict:
    """Fetch a GitHub issue and reject pull requests."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}"

    response = requests.get(
        url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=20,
    )
    response.raise_for_status()

    issue = response.json()

    if "pull_request" in issue:
        raise ValueError(f"#{number} is a pull request, not an issue.")

    return issue


def prepare_isolated_repository(number: int) -> tuple[Path, str]:
    """Clone upstream into a fresh, isolated evaluation directory."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    evaluation_repo_name = (
        f"requests_eval_issue_{number}_{EVALUATION_VERSION}"
    )
    repo_dir = WORKSPACE / f"{OWNER}_{evaluation_repo_name}"

    if repo_dir.exists():
        raise FileExistsError(
            f"Evaluation folder already exists: {repo_dir}\n"
            f"Change EVALUATION_VERSION from '{EVALUATION_VERSION}' "
            "to a new version before running again. "
            "The existing folder was not modified."
        )

    print(f"[Setup] Cloning {OWNER}/{REPO} into {repo_dir}")

    Repo.clone_from(
        f"https://github.com/{OWNER}/{REPO}.git",
        repo_dir,
        depth=1,
    )

    return repo_dir, evaluation_repo_name


def evaluate_issue(number: int) -> dict:
    """Evaluate one issue against an isolated repository clone."""
    started = time.time()

    record = {
        "issue_number": number,
        "issue_url": f"https://github.com/{OWNER}/{REPO}/issues/{number}",
        "workflow_executed": False,
        "error": "",
    }

    try:
        issue = fetch_issue(OWNER, REPO, number)

        title = issue.get("title") or ""
        body = issue.get("body") or ""

        record.update({
            "title": title,
            "issue_state": issue.get("state", "unknown"),
        })

        print("\n" + "=" * 70)
        print(f"EVALUATING {OWNER}/{REPO}#{number}: {title}")
        print("=" * 70)
        print("Remote Git automation: DISABLED")
        print("Local Git automation: DISABLED")
        print("Repository under evaluation: isolated clone")

        repo_dir, evaluation_repo_name = prepare_isolated_repository(number)

        # The workflow resolves the repository as:
        # workspace/{owner}_{repo}
        # Therefore, owner + repo match the isolated clone directory.
        initial_state = {
            "owner": OWNER,
            "repo": evaluation_repo_name,
            "issue_number": number,
            "issue_title": title,
            "issue_body": body,
            "issue_url": record["issue_url"],
            "base_branch": "main",
            "enable_local_git_automation": False,
            "enable_remote_git_automation": False,
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

        print(f"[Setup] Isolated repository ready: {repo_dir}")
        print("[Workflow] Starting LangGraph...\n")

        result = build_graph().invoke(initial_state)

        patches = result.get("generated_patches") or []
        applications = result.get("patch_application_results") or []
        validations = result.get("patch_validation_results") or []
        test_result = result.get("repository_test_result") or {}
        plan = result.get("implementation_plan") or {}

        applied = [
            item for item in applications
            if item.get("applied", False)
        ]

        # Do not report a test failure when the test node never ran.
        test_command = test_result.get("command", "")
        tests_skipped = test_result.get("skipped", False)
        tests_ran = bool(test_command) and not tests_skipped

        if tests_skipped:
            test_status = "SKIPPED"
        elif not tests_ran:
            test_status = "NOT RUN"
        elif test_result.get("success", False):
            test_status = "PASSED"
        else:
            test_status = "FAILED"

        record.update({
            "workflow_executed": True,
            "final_status": result.get("final_status", "unknown"),
            "retry_count": result.get("retry_count", 0),
            "plan_summary": plan.get("summary", ""),
            "planned_changes": plan.get("files_to_modify", []),
            "patches_generated": len(patches),
            "patches": [
                {
                    "file_path": patch.get("file_path", ""),
                    "explanation": patch.get("explanation", ""),
                }
                for patch in patches
            ],
            "patches_validated": sum(
                1 for item in validations
                if item.get("valid", False)
            ),
            "patches_applied": len(applied),
            "application_results": applications,
            "repository_tests": {
                "status": test_status,
                "success": (
                    test_result.get("success")
                    if tests_ran else None
                ),
                "skipped": tests_skipped,
                "ran": tests_ran,
                "exit_code": test_result.get("exit_code"),
                "command": test_command,
                "stdout": test_result.get("stdout", ""),
                "stderr": test_result.get("stderr", ""),
            },
            "evaluation_repository": str(repo_dir),
            "remote_git_automation": "disabled",
            "local_git_automation": "disabled",
        })

    except KeyboardInterrupt:
        print("\n[Evaluation] Interrupted by user.")
        record["error"] = "Interrupted by user."
        raise

    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        print(f"\n[Evaluation Error] {record['error']}")

    finally:
        record["duration_seconds"] = round(time.time() - started, 2)

    return record


def main() -> None:
    results = []

    for number in ISSUE_NUMBERS:
        result = evaluate_issue(number)
        results.append(result)

        # Save after each issue so completed results are preserved.
        REPORT_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n[Report] Saved to {REPORT_PATH}")

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    for result in results:
        print(
            f"Issue: #{result['issue_number']} — "
            f"{result.get('title', 'Title unavailable')}"
        )
        print(f"Workflow executed: {result['workflow_executed']}")
        print(f"Final status: {result.get('final_status', 'not available')}")
        print(f"Patches generated: {result.get('patches_generated', 0)}")
        print(f"Patches applied: {result.get('patches_applied', 0)}")

        tests = result.get("repository_tests", {})
        print(f"Repository tests: {tests.get('status', 'NOT RUN')}")

        if tests.get("ran"):
            print(f"Test command: {tests.get('command', '')}")
            print(f"Test exit code: {tests.get('exit_code')}")

        if result.get("error"):
            print(f"Error: {result['error']}")

        print("-" * 50)

    print(f"\nFull report: {REPORT_PATH}")
    print("Issue resolution is not proven by syntax validation alone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
