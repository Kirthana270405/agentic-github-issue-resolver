
import ast
from pathlib import Path

from app.agents.code_generator import GeneratedChange
from app.agents.patch_validator import PatchValidator


def test_valid_patch_is_accepted(tmp_path: Path) -> None:
    """A valid, exact Python replacement should pass validation."""

    file_path = tmp_path / "sample.py"
    original_code = (
        "def greet():\n"
        "    return 'hello'\n"
    )
    new_code = (
        "def greet():\n"
        "    return 'hello world'\n"
    )
    file_path.write_text(original_code, encoding="utf-8")

    change = GeneratedChange(
        file_path=str(file_path),
        original_code="    return 'hello'",
        new_code="    return 'hello world'",
        explanation="Update the greeting.",
    )

    valid, message = PatchValidator().validate(
        change,
        repo_root=tmp_path,
    )

    assert valid, message
    assert "valid" in message.lower()


def test_patch_with_missing_original_is_rejected(tmp_path: Path) -> None:
    """A patch whose original snippet is absent should be rejected."""

    file_path = tmp_path / "sample.py"
    file_path.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )

    change = GeneratedChange(
        file_path=str(file_path),
        original_code="return 'missing'",
        new_code="return 'updated'",
        explanation="Test a missing snippet.",
    )

    valid, message = PatchValidator().validate(
        change,
        repo_root=tmp_path,
    )

    assert not valid
    assert "not found" in message.lower()


def test_patch_outside_repository_is_rejected(tmp_path: Path) -> None:
    """A patch targeting a file outside the repository should be rejected."""

    repo_root = tmp_path / "repo"
    outside_root = tmp_path / "outside"
    repo_root.mkdir()
    outside_root.mkdir()

    file_path = outside_root / "sample.py"
    file_path.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )

    change = GeneratedChange(
        file_path=str(file_path),
        original_code="return 'hello'",
        new_code="return 'updated'",
        explanation="Test repository boundary validation.",
    )

    valid, message = PatchValidator().validate(
        change,
        repo_root=repo_root,
    )

    assert not valid
    assert "outside the repository" in message.lower()


def test_invalid_python_replacement_is_rejected(tmp_path: Path) -> None:
    """A replacement that breaks Python syntax should be rejected."""

    file_path = tmp_path / "sample.py"
    file_path.write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )

    change = GeneratedChange(
        file_path=str(file_path),
        original_code="    return 'hello'",
        new_code="    return 'hello'\n  invalid syntax",
        explanation="Test syntax validation.",
    )

    valid, message = PatchValidator().validate(
        change,
        repo_root=tmp_path,
    )

    assert not valid
    assert "syntax" in message.lower()


def test_valid_replacement_preserves_python_syntax(tmp_path: Path) -> None:
    """The expected replacement should produce parseable Python."""

    file_path = tmp_path / "sample.py"
    original_code = "def add(a, b):\n    return a + b\n"
    file_path.write_text(original_code, encoding="utf-8")

    change = GeneratedChange(
        file_path=str(file_path),
        original_code="return a + b",
        new_code="return a - b",
        explanation="Change addition to subtraction.",
    )

    valid, message = PatchValidator().validate(
        change,
        repo_root=tmp_path,
    )

    assert valid, message

    modified_code = original_code.replace(
        change.original_code,
        change.new_code,
        1,
    )
    ast.parse(modified_code)
