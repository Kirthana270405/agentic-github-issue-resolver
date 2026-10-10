
from pathlib import Path

import app.workflow.graph as workflow_graph
import app.workflow.nodes as nodes
from app.agents.code_generator import GeneratedChange


def test_full_graph_applies_patch_and_runs_repository_tests(
    tmp_path, monkeypatch
):
    # Create an isolated temporary repository.
    repo = tmp_path / "test_repo"
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

    # Point workflow nodes at the temporary repository.
    monkeypatch.setattr(nodes, "_repo_root", lambda state: repo)

    # Avoid GitHub and LLM calls.
    monkeypatch.setattr(
        workflow_graph,
        "analyze_issue_node",
        lambda state: {
            "problem": "Update VALUE to 2",
            "expected_behavior": "VALUE must equal 2",
            "likely_components": [],
            "technical_constraints": [],
            "acceptance_criteria": [],
        },
    )

    monkeypatch.setattr(
        workflow_graph,
        "retrieve_code_node",
        lambda state: {
            "relevant_code": [
                {
                    "file_path": str(source_file),
                    "content": "VALUE = 1\n",
                }
            ]
        },
    )

    monkeypatch.setattr(
        workflow_graph,
        "planning_node",
        lambda state: {
            "implementation_plan": {
                "summary": "Update the sample constant",
                "decision": "CHANGE_REQUIRED",
                "files_to_modify": [
                    {
                        "file_path": "sample.py",
                        "change": "Change VALUE from 1 to 2",
                        "reason": "Required by the issue",
                    }
                ],
            }
        },
    )

    # Return a deterministic patch instead of calling Ollama.
    class FakeGenerator:
        def generate(self, **kwargs):
            return GeneratedChange(
                file_path=kwargs["file_path"],
                original_code="VALUE = 1",
                new_code="VALUE = 2",
                explanation="Updated VALUE to match the requirement.",
            )

    monkeypatch.setattr(nodes, "CodeGeneratorAgent", FakeGenerator)

    graph = workflow_graph.build_graph()

    initial_state = {
        "owner": "test",
        "repo": "repo",
        "issue_title": "Update sample value",
        "issue_body": "VALUE should equal 2",
        "retry_count": 0,
        "debug_analysis": {},
    }

    result = graph.invoke(initial_state)

    # Confirm the patch was generated and applied.
    assert source_file.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert result["generated_patches"]
    assert any(
        item.get("applied", False)
        for item in result["patch_application_results"]
    )

    # Confirm repository tests ran and passed.
    test_result = result["repository_test_result"]
    assert test_result["success"], (
        test_result.get("stdout", "")
        + "\n"
        + test_result.get("stderr", "")
    )
    assert result["final_status"] == "success"
