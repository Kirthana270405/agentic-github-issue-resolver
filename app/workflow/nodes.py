
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

from app.agents.code_generator import CodeGeneratorAgent, GeneratedChange
from app.agents.debugger import DebuggerAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.patch_applier import PatchApplier
from app.agents.patch_validator import PatchValidator
from app.agents.planner import PlannerAgent
from app.workflow.state import WorkflowState


MAX_RETRIES = 2


def _repo_root(state: WorkflowState) -> Path:
    """Resolve the target repository."""
    owner = str(state.get("owner", "")).strip()
    repo = str(state.get("repo", "")).strip()

    if not owner or not repo:
        raise ValueError("Both owner and repo must be provided.")

    return (Path("workspace") / f"{owner}_{repo}").resolve()


def _safe_repo_file(repo_root: Path, file_path: str) -> Path | None:
    """Resolve a target file while preventing paths outside the repository."""
    if not file_path or not file_path.strip():
        return None

    root = repo_root.resolve()
    raw_path = file_path.strip().replace("\\", "/")

    try:
        supplied = Path(raw_path)

        if supplied.is_absolute():
            candidate = supplied.resolve()
        else:
            parts = list(supplied.parts)

            # Handle paths such as workspace/psf_requests/src/module.py.
            if root.name in parts:
                index = len(parts) - 1 - parts[::-1].index(root.name)
                relative_parts = parts[index + 1:]

                if not relative_parts:
                    return None

                candidate = root.joinpath(*relative_parts).resolve()
            else:
                candidate = (root / supplied).resolve()

        candidate.relative_to(root)

        if not candidate.is_file():
            return None

        return candidate

    except (OSError, ValueError, RuntimeError):
        return None


# ============================================================
# NODE 1 — ANALYZE ISSUE
# ============================================================

def analyze_issue_node(state: WorkflowState) -> dict:
    """Analyze the GitHub issue."""
    print("\n[Node] Analyzing GitHub issue...")

    title = str(state.get("issue_title", "") or "").strip()
    body = str(state.get("issue_body", "") or "").strip()

    if not title and not body:
        return {
            "problem": "",
            "expected_behavior": "",
            "likely_components": [],
            "technical_constraints": [],
            "acceptance_criteria": [],
            "error": "Issue title and body are both empty.",
        }

    try:
        analysis = IssueAnalyzer().analyze(title=title, body=body)
    except Exception as exc:
        print(f"[Node] Issue analysis failed: {exc}")
        return {
            "problem": title or body,
            "expected_behavior": "Insufficient information; do not guess.",
            "likely_components": [],
            "technical_constraints": [],
            "acceptance_criteria": [],
            "error": f"Issue analysis failed: {type(exc).__name__}",
        }

    print(f"[Node] Problem: {analysis.problem}")
    print(f"[Node] Expected behavior: {analysis.expected_behavior}")

    return {
        "problem": analysis.problem,
        "expected_behavior": analysis.expected_behavior,
        "likely_components": analysis.likely_components,
        "technical_constraints": analysis.technical_constraints,
        "acceptance_criteria": analysis.acceptance_criteria,
        "error": "",
    }


# ============================================================
# NODE 2 — RETRIEVE RELEVANT CODE
# ============================================================

class CodeChunker:
    def __init__(self, chunk_size: int = 80):
        self.chunk_size = chunk_size

    def chunk_file(self, file_path: str) -> list[dict]:
        try:
            with open(file_path, "r", encoding="utf-8") as source:
                lines = source.readlines()
        except (OSError, UnicodeDecodeError):
            return []

        chunks = []

        for start in range(0, len(lines), self.chunk_size):
            end = min(start + self.chunk_size, len(lines))

            chunks.append({
                "file_path": file_path,
                "start_line": start + 1,
                "end_line": end,
                "content": "".join(lines[start:end]),
            })

        return chunks



def retrieve_code_node(state: WorkflowState) -> dict:
    """Retrieve repository code using issue-aware lexical ranking."""
    print("\n[Node] Retrieving relevant repository code...")

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        print(f"[Node] {exc}")
        return {"relevant_code": []}

    if not repo_root.is_dir():
        print(f"[Node] Repository not found: {repo_root}")
        return {"relevant_code": []}

    excluded_dirs = {
        ".git", "__pycache__", ".venv", "venv",
        "node_modules", "build", "dist", ".tox",
        "docs", "examples",
    }

    source_files = []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [
            directory for directory in dirs
            if directory not in excluded_dirs
        ]

        for filename in files:
            if filename.endswith(".py"):
                source_files.append(os.path.join(root, filename))

    chunker = CodeChunker(chunk_size=80)
    all_chunks = []

    for file_path in source_files:
        all_chunks.extend(chunker.chunk_file(file_path))

    query = " ".join([
        str(state.get("problem", "")),
        str(state.get("expected_behavior", "")),
        " ".join(state.get("likely_components", [])),
        " ".join(state.get("acceptance_criteria", [])),
        str(state.get("issue_title", "")),
        str(state.get("issue_body", "")),
    ]).lower()

    stop_words = {
        "the", "and", "for", "with", "from", "that", "this",
        "when", "where", "what", "how", "should", "would",
        "could", "into", "have", "has", "had", "are", "was",
        "were", "will", "can", "not", "use", "using", "please",
        "issue", "description", "title", "behavior", "implement",
        "requested", "expected", "their", "they", "them",
        "does", "doesn", "always", "correctly",
    }

    tokenize = lambda text: re.findall(
        r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()
    )

    query_words = {
        word for word in tokenize(query)
        if len(word) >= 3 and word not in stop_words
    }

    # Include common singular/plural variants.
    query_words |= {
        word[:-1]
        for word in list(query_words)
        if word.endswith("s") and len(word) > 4
    }

    if not query_words:
        print("[Node] No useful query keywords were found.")
        return {"relevant_code": []}

    scored_chunks = []

    for chunk in all_chunks:
        content = chunk["content"].lower()
        relative_path = (
            Path(chunk["file_path"])
            .relative_to(repo_root)
            .as_posix()
            .lower()
        )

        path_words = set(tokenize(relative_path))
        content_words = tokenize(content)
        content_word_set = set(content_words)

        score = 0

        # File names are useful clues, but must not dominate code evidence.
        for word in query_words:
            if word in path_words:
                score += 4
            elif any(
                word in part
                for part in path_words
                if len(part) >= 4
            ):
                score += 2

            # Reward actual implementation evidence in the code.
            if word in content_word_set:
                score += min(content_words.count(word), 5)

        # Exact issue phrases provide stronger evidence than isolated words.
        issue_body = str(state.get("issue_body", "")).lower()
        for phrase in (
            "response body",
            "response content",
            "http response",
            "status code",
        ):
            if phrase in issue_body and phrase in content:
                score += 5

        # Favor executable code over chunks consisting mostly of comments.
        if "def " in content or "class " in content:
            score += 2

        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)

    top_chunks = [chunk for _, chunk in scored_chunks[:5]]

    print(f"[Node] Scanned {len(source_files)} Python files.")
    print(f"[Node] Scored {len(scored_chunks)} relevant code chunks.")
    print(f"[Node] Retrieved {len(top_chunks)} relevant code chunks.")

    for rank, chunk in enumerate(top_chunks, start=1):
        relative_path = (
            Path(chunk["file_path"]).relative_to(repo_root)
        )
        print(
            f"  {rank}. {relative_path} "
            f"(line {chunk['start_line']})"
        )

    return {"relevant_code": top_chunks}


# ============================================================
# NODE 3 — CREATE IMPLEMENTATION PLAN
# ============================================================



def planning_node(state: WorkflowState) -> dict:
    print("\n[Node] Creating implementation plan...")

    if state.get("error"):
        print("[Node] Skipping planning because issue analysis failed.")

        return {
            "implementation_plan": {
                "summary": "Issue analysis failed; no changes proposed.",
                "decision": "INSUFFICIENT_CONTEXT",
                "files_to_modify": [],
            },
            "final_status": "planning_failed",
        }

    planner = PlannerAgent()

    plan = planner.plan(
        problem=state.get("problem", ""),
        expected_behavior=state.get("expected_behavior", ""),
        likely_components=state.get("likely_components", []),
        acceptance_criteria=state.get("acceptance_criteria", []),
        relevant_code=state.get("relevant_code", []),
    )

    print(f"[Node] Plan: {plan.summary}")
    print(f"[Node] Decision: {plan.decision}")
    print(f"[Node] Files proposed: {len(plan.files_to_modify)}")

    for index, change in enumerate(plan.files_to_modify, start=1):
        print(f"\n[Plan {index}]")
        print(f"  File: {change.file_path}")
        print(f"  Change: {change.change}")
        print(f"  Reason: {change.reason}")

    if plan.decision == "ALREADY_SUPPORTED":
        final_status = "no_change_needed"
    elif plan.decision == "INSUFFICIENT_CONTEXT":
        final_status = "insufficient_context"
    elif plan.decision == "CHANGE_REQUIRED" and plan.files_to_modify:
        final_status = ""
    else:
        final_status = "insufficient_context"

    if not plan.files_to_modify:
        print("[Node] No changes proposed by the planner.")

    return {
        "implementation_plan": plan.model_dump(),
        "final_status": final_status,
    }



# ============================================================
# NODE 4 — GENERATE CODE CHANGES
# ============================================================

def code_generation_node(state: WorkflowState) -> dict:
    """Generate targeted patches for the planned changes."""
    print("\n[Node] Generating code changes...")

    problem = state.get("problem", "")
    expected_behavior = state.get("expected_behavior", "")
    retry_count = state.get("retry_count", 0)
    debug_analysis = state.get("debug_analysis", {})

    if (
        retry_count > 0
        and isinstance(debug_analysis, dict)
        and debug_analysis.get("category") == "code"
        and debug_analysis.get("retry_recommended")
    ):
        problem += (
            "\n\nPrevious test failure diagnosis:\n"
            f"{debug_analysis.get('root_cause', '')}\n\n"
            "Suggested fix:\n"
            f"{debug_analysis.get('suggested_fix', '')}\n\n"
            "Make only the smallest relevant correction."
        )

    plan = state.get("implementation_plan", {})

    if not plan:
        print("[Node] No implementation plan found.")
        return {"generated_patches": []}

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        print(f"[Node] {exc}")
        return {"generated_patches": []}

    generator = CodeGeneratorAgent()
    generated_patches = []

    for file_info in plan.get("files_to_modify", []):
        if not isinstance(file_info, dict):
            print(f"[Node] Skipping malformed plan entry: {file_info!r}")
            continue

        target_path = file_info.get("file_path", "")
        planned_change = file_info.get("change", "")
        reason = file_info.get("reason", "")

        resolved_path = _safe_repo_file(repo_root, target_path)

        if resolved_path is None:
            print(f"[Node] Rejected missing or unsafe target: {target_path}")
            continue

        try:
            file_content = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"[Node] Could not read {target_path}: {exc}")
            continue

        if not file_content.strip():
            print(f"[Node] Source file is empty: {target_path}")
            continue

        try:
            change = generator.generate(
                problem=problem,
                expected_behavior=expected_behavior,
                file_path=str(resolved_path),
                planned_change=planned_change,
                reason=reason,
                file_content=file_content,
            )
        except Exception as exc:
            print(f"[Node] Generator failed for {target_path}: {exc}")
            continue

        if change is None:
            print(f"[Node] Generator returned no result: {target_path}")
            continue

        if not change.original_code.strip() or not change.new_code.strip():
            print(f"[Node] Rejected empty patch: {target_path}")
            print(f"[Node] Generator explanation: {change.explanation}")
            continue

        if change.original_code == change.new_code:
            print(f"[Node] Rejected no-op patch: {target_path}")
            print(f"[Node] Generator explanation: {change.explanation}")
            continue

        occurrences = file_content.count(change.original_code)

        if occurrences != 1:
            print(f"[Node] Rejected ambiguous or unmatched patch: {target_path}")
            print(f"[Node] Original snippet occurrences: {occurrences}")
            continue

        updated_content = file_content.replace(
            change.original_code,
            change.new_code,
            1,
        )

        try:
            ast.parse(updated_content, filename=str(resolved_path))
        except SyntaxError as exc:
            print(f"[Node] Rejected syntactically invalid patch: {exc}")
            continue

        patch_data = change.model_dump()
        patch_data["file_path"] = str(resolved_path)

        generated_patches.append(patch_data)
        print(f"[Node] Generated valid patch for: {target_path}")

    if not generated_patches:
        print("[Node] No valid patches were generated.")

    return {"generated_patches": generated_patches}


# ============================================================
# NODE 5 — VALIDATE PATCHES
# ============================================================

def patch_validation_node(state: WorkflowState) -> dict:
    print("\n[Node] Validating generated patches...")

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        return {
            "patch_validation_results": [{
                "file_path": "",
                "valid": False,
                "message": str(exc),
            }]
        }

    validator = PatchValidator()
    validation_results = []

    for patch in state.get("generated_patches", []):
        file_path = patch.get("file_path", "")

        try:
            patch_object = GeneratedChange.model_validate(patch)

            valid, message = validator.validate(
                patch_object,
                repo_root=repo_root,
            )
        except Exception as exc:
            valid = False
            message = f"Validation error: {exc}"

        result = {
            "file_path": file_path,
            "valid": bool(valid),
            "message": str(message),
        }

        validation_results.append(result)

        print(
            f"[Node] Patch {'VALID' if valid else 'INVALID'}: "
            f"{file_path} — {message}"
        )

    return {"patch_validation_results": validation_results}


# ============================================================
# NODE 6 — APPLY VALID PATCHES
# ============================================================

def patch_application_node(state: WorkflowState) -> dict:
    print("\n[Node] Applying valid patches...")

    patches = state.get("generated_patches", [])
    validations = state.get("patch_validation_results", [])

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        return {
            "patch_application_results": [{
                "file_path": "",
                "applied": False,
                "message": str(exc),
            }]
        }

    validator = PatchValidator()
    applier = PatchApplier()
    results = []

    validation_by_path = {
        item.get("file_path"): item
        for item in validations
    }

    for patch in patches:
        file_path = patch.get("file_path", "")
        validation = validation_by_path.get(file_path, {})

        if not validation.get("valid", False):
            results.append({
                "file_path": file_path,
                "applied": False,
                "message": "Skipped because patch validation did not pass.",
            })
            continue

        try:
            patch_object = GeneratedChange.model_validate(patch)

            # Revalidate immediately before writing.
            valid, message = validator.validate(
                patch_object,
                repo_root=repo_root,
            )

            if not valid:
                results.append({
                    "file_path": file_path,
                    "applied": False,
                    "message": f"Revalidation failed: {message}",
                })
                continue

            applied, message = applier.apply(
                patch_object,
                repo_root=repo_root,
            )

            results.append({
                "file_path": file_path,
                "applied": bool(applied),
                "message": message,
            })

        except Exception as exc:
            results.append({
                "file_path": file_path,
                "applied": False,
                "message": f"Application error: {exc}",
            })

    for result in results:
        print(
            f"[Node] {'APPLIED' if result['applied'] else 'NOT APPLIED'}: "
            f"{result['file_path']} — {result['message']}"
        )

    return {"patch_application_results": results}


# ============================================================
# NODE 7 — FINAL VALIDATION
# ============================================================

def final_validation_node(state: WorkflowState) -> dict:
    print("\n[Node] Validating modified files...")

    application_results = state.get("patch_application_results", [])
    test_results = []

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        return {
            "test_results": [],
            "final_status": "validation_failed",
            "error": str(exc),
        }

    for result in application_results:
        file_path = result.get("file_path", "")

        if not result.get("applied", False):
            test_results.append({
                "file_path": file_path,
                "valid": False,
                "message": "Patch was not applied.",
            })
            continue

        try:
            source_path = Path(file_path).resolve()
            source_path.relative_to(repo_root)

            source = source_path.read_text(encoding="utf-8")
            compile(source, str(source_path), "exec")

            test_results.append({
                "file_path": str(source_path),
                "valid": True,
                "message": "Python syntax validation passed.",
            })

        except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as exc:
            test_results.append({
                "file_path": file_path,
                "valid": False,
                "message": str(exc),
            })

    applied_count = sum(
        1 for result in application_results
        if result.get("applied", False)
    )

    valid_count = sum(
        1 for result in test_results
        if result.get("valid", False)
    )

    if applied_count == 0:
        final_status = "no_patches_applied"
    elif valid_count == applied_count:
        final_status = "success"
    else:
        final_status = "validation_failed"

    print(f"[Node] Final status: {final_status}")

    return {
        "test_results": test_results,
        "final_status": final_status,
    }


# ============================================================
# NODE 8 — RUN REPOSITORY TESTS
# ============================================================

def test_execution_node(state: WorkflowState) -> dict:
    """Run tests only when a patch was applied and syntax is valid."""
    application_results = state.get("patch_application_results", [])

    applied_count = sum(
        1 for result in application_results
        if result.get("applied", False)
    )

    if applied_count == 0:
        message = "Repository tests skipped because no patch was applied."
        print(f"\n[Node] {message}")

        return {
            "repository_test_result": {
                "success": False,
                "skipped": True,
                "exit_code": None,
                "stdout": "",
                "stderr": message,
                "command": "",
            }
        }

    if state.get("final_status") != "success":
        message = "Repository tests skipped because syntax validation failed."
        print(f"\n[Node] {message}")

        return {
            "repository_test_result": {
                "success": False,
                "skipped": True,
                "exit_code": None,
                "stdout": "",
                "stderr": message,
                "command": "",
            }
        }

    try:
        repo_root = _repo_root(state)
    except ValueError as exc:
        return {
            "repository_test_result": {
                "success": False,
                "skipped": True,
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "command": "",
            }
        }

    if not repo_root.is_dir():
        return {
            "repository_test_result": {
                "success": False,
                "skipped": False,
                "exit_code": None,
                "stdout": "",
                "stderr": f"Repository not found: {repo_root}",
                "command": "",
            }
        }

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "--tb=short",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        return {
            "repository_test_result": {
                "success": result.returncode == 0,
                "skipped": False,
                "exit_code": result.returncode,
                "stdout": result.stdout[-12000:],
                "stderr": result.stderr[-4000:],
                "command": "python -m pytest tests -q --tb=short",
            }
        }

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        return {
            "repository_test_result": {
                "success": False,
                "skipped": False,
                "exit_code": None,
                "stdout": stdout[-12000:],
                "stderr": (
                    "Repository tests exceeded the 180-second timeout. "
                    + stderr[-4000:]
                ),
                "command": "python -m pytest tests -q --tb=short",
            }
        }


# ============================================================
# NODE 9 — DEBUG TEST FAILURES
# ============================================================

def debugging_node(state: WorkflowState) -> dict:
    print("\n[Node] Analyzing repository test failures...")

    test_result = state.get("repository_test_result", {})

    if test_result.get("skipped"):
        diagnosis = {
            "category": "unknown",
            "root_cause": test_result.get(
                "stderr", "Tests were skipped."
            ),
            "suggested_fix": "",
            "retry_recommended": False,
        }
    else:
        diagnosis = DebuggerAgent().analyze(test_result)

        if hasattr(diagnosis, "model_dump"):
            diagnosis = diagnosis.model_dump()

    if not isinstance(diagnosis, dict):
        diagnosis = {
            "category": "unknown",
            "root_cause": "Debugger returned an invalid diagnosis.",
            "suggested_fix": "",
            "retry_recommended": False,
        }

    print(f"[Debugger] Diagnosis: {diagnosis}")

    return {"debug_analysis": diagnosis}


# ============================================================
# NODE 10 — PREPARE RETRY
# ============================================================

def prepare_retry_node(state: WorkflowState) -> dict:
    """Clear outputs from the previous attempt before regenerating."""
    retry_count = state.get("retry_count", 0) + 1

    print(f"\n[Node] Preparing retry {retry_count}/{MAX_RETRIES}")

    return {
        "retry_count": retry_count,
        "generated_patches": [],
        "patch_validation_results": [],
        "patch_application_results": [],
        "test_results": [],
        "repository_test_result": {},
        "final_status": "",
        "error": "",
    }
