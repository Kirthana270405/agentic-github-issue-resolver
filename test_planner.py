
from app.agents.planner import (
    FileChange,
    ImplementationPlan,
    PlannerAgent,
)


def test_implementation_plan_defaults_to_no_changes():
    plan = ImplementationPlan(summary="No changes needed.")

    assert plan.summary == "No changes needed."
    assert plan.files_to_modify == []


def test_implementation_plan_accepts_file_changes():
    change = FileChange(
        file_path="src/example.py",
        change="Update the validation logic.",
        reason="The current validation misses an invalid input.",
    )

    plan = ImplementationPlan(
        summary="Improve input validation.",
        files_to_modify=[change],
    )

    assert len(plan.files_to_modify) == 1
    assert plan.files_to_modify[0].file_path == "src/example.py"
    assert plan.files_to_modify[0].change == "Update the validation logic."


def test_planner_returns_empty_plan_without_repository_context():
    planner = PlannerAgent()

    plan = planner.plan(
        problem="Fix a bug.",
        expected_behavior="Handle invalid input safely.",
        likely_components=[],
        acceptance_criteria=[],
        relevant_code=[],
    )

    assert isinstance(plan, ImplementationPlan)
    assert plan.files_to_modify == []
    assert "Insufficient repository context" in plan.summary


def test_planner_rejects_unretrieved_paths(monkeypatch):
    retrieved_code = [
        {
            "file_path": "src/example.py",
            "content": "def example():\n    return True\n",
        }
    ]

    proposed_plan = ImplementationPlan(
        summary="Test path validation.",
        files_to_modify=[
            FileChange(
                file_path="src/other.py",
                change="Modify another file.",
                reason="Testing path rejection.",
            ),
            FileChange(
                file_path="src/example.py",
                change="Update the return value.",
                reason="Testing an allowed path.",
            ),
        ],
    )

    def fake_chat(**kwargs):
        return {
            "message": {
                "content": proposed_plan.model_dump_json(),
            }
        }

    monkeypatch.setattr(
        "app.agents.planner.ollama.chat",
        fake_chat,
    )

    planner = PlannerAgent()

    plan = planner.plan(
        problem="Update example behavior.",
        expected_behavior="Return the expected value.",
        likely_components=["example"],
        acceptance_criteria=["Use the retrieved file."],
        relevant_code=retrieved_code,
    )

    assert isinstance(plan, ImplementationPlan)
    assert len(plan.files_to_modify) == 1
    assert plan.files_to_modify[0].file_path == "src/example.py"


def test_planner_rejects_duplicate_file_changes(monkeypatch):
    retrieved_code = [
        {
            "file_path": "src/example.py",
            "content": "def example():\n    return True\n",
        }
    ]

    proposed_plan = ImplementationPlan(
        summary="Test duplicate paths.",
        files_to_modify=[
            FileChange(
                file_path="src/example.py",
                change="Change one.",
                reason="First proposal.",
            ),
            FileChange(
                file_path="src/example.py",
                change="Change two.",
                reason="Duplicate proposal.",
            ),
        ],
    )

    def fake_chat(**kwargs):
        return {
            "message": {
                "content": proposed_plan.model_dump_json(),
            }
        }

    monkeypatch.setattr(
        "app.agents.planner.ollama.chat",
        fake_chat,
    )

    plan = PlannerAgent().plan(
        problem="Test duplicate paths.",
        expected_behavior="Plan a single change per file.",
        likely_components=[],
        acceptance_criteria=[],
        relevant_code=retrieved_code,
    )

    assert len(plan.files_to_modify) == 1
    assert plan.files_to_modify[0].file_path == "src/example.py"
