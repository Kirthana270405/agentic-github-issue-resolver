
import ast
import json
import re

import ollama
from pydantic import BaseModel, ValidationError


class GeneratedChange(BaseModel):
    file_path: str
    original_code: str
    new_code: str
    explanation: str


class CodeGeneratorAgent:
    MODEL = "qwen3:1.7b"
    MAX_ATTEMPTS = 2

    def __init__(self):
        self.model = self.MODEL

    def generate(
        self,
        problem: str,
        expected_behavior: str,
        file_path: str,
        planned_change: str,
        reason: str,
        file_content: str,
    ) -> GeneratedChange:
        """Generate a targeted replacement and validate its result."""

        if not file_content.strip():
            return self._empty_change(file_path, "The target file is empty.")

        if not planned_change.strip():
            return self._empty_change(
                file_path,
                "The implementation plan contains no specific change.",
            )

        last_result = self._empty_change(
            file_path,
            "Could not generate a valid patch.",
        )

        for attempt in range(self.MAX_ATTEMPTS):
            retry_instruction = ""
            if attempt:
                retry_instruction = """
The previous attempt did not produce a usable patch.
Try a different, small, meaningful implementation supported by the
issue and plan. Do not duplicate existing methods or unrelated code.
If no safe change can be determined, return empty original_code
and new_code and explain why.
"""

            prompt = f"""
You are a careful software engineer modifying an existing Python project.

ISSUE:
{problem}

EXPECTED BEHAVIOR:
{expected_behavior}

TARGET FILE:
{file_path}

PLANNED CHANGE:
{planned_change}

REASON:
{reason}

EXISTING FILE:
--- BEGIN FILE ---
{file_content}
--- END FILE ---

{retry_instruction}

Return one JSON object with these string fields:
- file_path: the target file path.
- original_code: an exact, contiguous snippet copied from the file.
- new_code: the complete replacement for that snippet.
- explanation: a concise explanation.

Rules:
1. Make only the planned change.
2. Copy original_code exactly, including indentation.
3. Do not use placeholders, ellipses, or Markdown fences.
4. Do not return the entire file.
5. Preserve unrelated behavior and imports.
6. Resulting Python must be syntactically valid.
7. Do not invent requirements.
8. Never introduce duplicate class methods.
9. If no safe change can be determined, return empty original_code
   and new_code.
10. Return valid JSON only.
"""

            schema = {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "original_code": {"type": "string"},
                    "new_code": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "file_path",
                    "original_code",
                    "new_code",
                    "explanation",
                ],
            }

            try:
                response = ollama.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Generate conservative, meaningful, targeted "
                                "Python patches. Return only valid JSON. "
                                "Do not duplicate existing methods or invent "
                                "behavior unsupported by the supplied context."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    format=schema,
                    think=False,
                    options={
                        "temperature": 0,
                        "num_predict": 2500,
                        "repeat_penalty": 1.1,
                    },
                )
            except Exception as exc:
                print(f"[CodeGenerator] Ollama error: {exc}")
                return self._empty_change(
                    file_path,
                    f"Ollama generation failed: {type(exc).__name__}.",
                )

            raw_output = response.get("message", {}).get("content", "")
            if not isinstance(raw_output, str) or not raw_output.strip():
                last_result = self._empty_change(
                    file_path,
                    "The model returned empty output.",
                )
                continue

            cleaned = raw_output.strip()
            cleaned = re.sub(
                r"^\s*```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()

            try:
                data = json.loads(cleaned)
                change = GeneratedChange.model_validate(data)
            except (
                json.JSONDecodeError,
                ValidationError,
                TypeError,
                ValueError,
            ) as exc:
                print(f"[CodeGenerator] Invalid model response: {exc}")
                last_result = self._empty_change(
                    file_path,
                    "The model returned an invalid patch response.",
                )
                continue

            original_code = change.original_code
            new_code = change.new_code.strip("\n")
            explanation = change.explanation.strip()

            if not original_code.strip() or not new_code.strip():
                last_result = self._empty_change(
                    file_path,
                    explanation or "The model returned an empty patch.",
                )
                continue

            if original_code == new_code:
                last_result = self._empty_change(
                    file_path,
                    "The model returned an unchanged patch.",
                )
                continue

            occurrences = file_content.count(original_code)
            if occurrences != 1:
                last_result = self._empty_change(
                    file_path,
                    "Original snippet must match exactly once; "
                    f"found {occurrences} occurrences.",
                )
                continue

            updated_content = file_content.replace(original_code, new_code, 1)

            # Validate the complete resulting file.
            if file_path.lower().endswith(".py"):
                try:
                    before_tree = ast.parse(file_content, filename=file_path)
                    after_tree = ast.parse(updated_content, filename=file_path)
                except SyntaxError as exc:
                    last_result = self._empty_change(
                        file_path,
                        f"Replacement produces invalid Python syntax: {exc}",
                    )
                    continue

                # Reject any newly introduced duplicate method in a class.
                before_methods = self._class_methods(before_tree)
                after_methods = self._class_methods(after_tree)

                duplicate = self._new_duplicate_method(
                    before_methods,
                    after_methods,
                )
                if duplicate:
                    last_result = self._empty_change(
                        file_path,
                        f"Patch introduces duplicate method {duplicate}.",
                    )
                    continue

            return GeneratedChange(
                file_path=file_path,
                original_code=original_code,
                new_code=new_code,
                explanation=(
                    explanation or "Generated a targeted code replacement."
                ),
            )

        print(
            f"[CodeGenerator] No valid patch after "
            f"{self.MAX_ATTEMPTS} attempts."
        )
        return last_result

    @staticmethod
    def _class_methods(tree: ast.AST) -> dict[str, list[str]]:
        """Map each class name to its directly declared method names."""

        result = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result[node.name] = [
                    item.name
                    for item in node.body
                    if isinstance(
                        item,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    )
                ]

        return result

    @staticmethod
    def _new_duplicate_method(
        before: dict[str, list[str]],
        after: dict[str, list[str]],
    ) -> str | None:
        """Identify duplicate methods introduced by a proposed patch."""

        for class_name, method_names in after.items():
            old_names = before.get(class_name, [])

            for method_name in set(method_names):
                old_count = old_names.count(method_name)
                new_count = method_names.count(method_name)

                if new_count > max(1, old_count):
                    return f"{class_name}.{method_name}"

        return None

    @staticmethod
    def _empty_change(
        file_path: str,
        explanation: str,
    ) -> GeneratedChange:
        """Return an unusable patch with its failure explanation."""

        return GeneratedChange(
            file_path=file_path,
            original_code="",
            new_code="",
            explanation=explanation,
        )
