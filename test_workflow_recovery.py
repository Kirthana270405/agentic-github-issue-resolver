
import importlib

import app.workflow.nodes as nodes
from app.agents.code_generator import GeneratedChange


def test_failed_tests_trigger_retry_and_second_test_run_succeeds(
    monkeypatch,
):
    workflow = importlib.import_module("app.workflow.graph")

    calls = {"generate": 0, "tests": 0, "debug": 0, "retry": 0}

    def analyze(state):
        return {}

    def retrieve(state):
        return {"relevant_code": [
            {"file_path": "sample.py", "content": "VALUE = 1\n"}
        ]}

    def plan(state):
        return {
            "implementation_plan": {
                "summary": "Correct VALUE",
                "decision": "CHANGE_REQUIRED",
                "files_to_modify": [
                    {
                        "file_path": "sample.py",
                        "change": "Correct VALUE",
                        "reason": "Required by the issue",
                    }
                ],
            }
        }

    def generate(state):
        calls["generate"] += 1
        return {"generated_patches": [{"file_path": "sample.py"}]}

    def validate(state):
        return {"patch_validation_results": [{"valid": True}]}

    def apply(state):
        return {"patch_application_results": [{"applied": True}]}

    def final_validate(state):
        return {"final_status": "success"}

    def run_tests(state):
        calls["tests"] += 1
        if calls["tests"] == 1:
            return {
                "repository_test_result": {
                    "success": False,
                    "skipped": False,
                    "output": "Simulated test failure",
                }
            }
        return {
            "repository_test_result": {
                "success": True,
                "skipped": False,
                "output": "All tests passed",
            }
        }

    def debug(state):
        calls["debug"] += 1
        return {
            "debug_analysis": {
                "category": "code",
                "retry_recommended": True,
            }
        }

    def prepare_retry(state):
        calls["retry"] += 1
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "generated_patches": [],
            "patch_validation_results": [],
            "patch_application_results": [],
            "test_results": [],
            "repository_test_result": {},
            "final_status": "",
        }

    replacements = {
        "analyze_issue_node": analyze,
        "retrieve_code_node": retrieve,
        "planning_node": plan,
        "code_generation_node": generate,
        "patch_validation_node": validate,
        "patch_application_node": apply,
        "final_validation_node": final_validate,
        "test_execution_node": run_tests,
        "debugging_node": debug,
        "prepare_retry_node": prepare_retry,
    }

    for name, replacement in replacements.items():
        monkeypatch.setattr(workflow, name, replacement)

    app = workflow.build_graph()
    result = app.invoke({
        "owner": "psf",
        "repo": "requests",
        "issue_title": "Correct VALUE",
        "issue_body": "VALUE must equal 2",
        "retry_count": 0,
        "debug_analysis": {},
    })

    assert calls["tests"] == 2
    assert calls["debug"] == 1
    assert calls["retry"] == 1
    assert calls["generate"] == 2
    assert result["retry_count"] == 1
    assert result["repository_test_result"]["success"] is True


def test_real_patch_failure_debug_retry_and_retest(tmp_path, monkeypatch):
    workflow_graph = importlib.import_module("app.workflow.graph")

    repo = tmp_path / "sample_repo"
    repo.mkdir()

    source_file = repo / "sample.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "from sample import VALUE\n\n"
        "def test_value():\n"
        "    assert VALUE == 2\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(nodes, "_repo_root", lambda state: repo)

    monkeypatch.setattr(
        workflow_graph,
        "analyze_issue_node",
        lambda state: {
            "problem": "VALUE must equal 2",
            "expected_behavior": "VALUE equals 2",
            "likely_components": [],
            "technical_constraints": [],
            "acceptance_criteria": ["VALUE == 2"],
            "error": "",
        },
    )

    monkeypatch.setattr(
        workflow_graph,
        "retrieve_code_node",
        lambda state: {
            "relevant_code": [
                {"file_path": "sample.py", "content": "VALUE = 1\n"}
            ]
        },
    )

    monkeypatch.setattr(
        workflow_graph,
        "planning_node",
        lambda state: {
            "implementation_plan": {
                "summary": "Set VALUE to 2",
                "decision": "CHANGE_REQUIRED",
                "files_to_modify": [
                    {
                        "file_path": "sample.py",
                        "change": "Correct VALUE",
                        "reason": "The test requires VALUE == 2",
                    }
                ],
            }
        },
    )

    generation_calls = []

    class FakeGenerator:
        def generate(self, **kwargs):
            current = kwargs["file_content"]
            generation_calls.append(current)

            if "VALUE = 1" in current:
                old, new = "VALUE = 1", "VALUE = 3"
            elif "VALUE = 3" in current:
                old, new = "VALUE = 3", "VALUE = 2"
            else:
                raise AssertionError(f"Unexpected source: {current!r}")

            return GeneratedChange(
                file_path=kwargs["file_path"],
                original_code=old,
                new_code=new,
                explanation="Deterministic test patch",
            )

    monkeypatch.setattr(nodes, "CodeGeneratorAgent", FakeGenerator)

    debug_calls = []

    def fake_debug(state):
        debug_calls.append(state["repository_test_result"])
        return {
            "debug_analysis": {
                "category": "code",
                "root_cause": "VALUE does not equal 2",
                "suggested_fix": "Set VALUE to 2",
                "retry_recommended": True,
            }
        }

    monkeypatch.setattr(workflow_graph, "debugging_node", fake_debug)

    app = workflow_graph.build_graph()
    result = app.invoke({
        "owner": "test",
        "repo": "sample",
        "issue_title": "Correct VALUE",
        "issue_body": "VALUE must equal 2",
        "retry_count": 0,
        "debug_analysis": {},
    })

    assert len(generation_calls) == 2
    assert len(debug_calls) == 1
    assert source_file.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert result["repository_test_result"]["success"] is True
    assert result["final_status"] == "success"
