import json
import re
from pathlib import PurePosixPath
from typing import Literal

import ollama
from pydantic import BaseModel, Field, ValidationError


class FileChange(BaseModel):
    file_path: str
    change: str
    reason: str


class ImplementationPlan(BaseModel):
    summary: str
    decision: Literal[
        "CHANGE_REQUIRED",
        "ALREADY_SUPPORTED",
        "INSUFFICIENT_CONTEXT",
    ] = "CHANGE_REQUIRED"
    files_to_modify: list[FileChange] = Field(default_factory=list)


class PlannerAgent:
    MODEL = "qwen3:1.7b"

    def plan(
        self,
        problem: str,
        expected_behavior: str,
        likely_components: list[str],
        acceptance_criteria: list[str],
        relevant_code: list[dict],
    ) -> ImplementationPlan:
        """Create a minimal plan grounded in retrieved repository code."""

        if not relevant_code:
            return ImplementationPlan(
                summary="Insufficient repository context to plan a safe change.",
                decision="INSUFFICIENT_CONTEXT",
                files_to_modify=[],
            )

        code_sections = []
        retrieved_paths = set()

        for item in relevant_code:
            path = str(item.get("file_path", "")).strip()
            content = str(item.get("content", ""))

            if not path or not content.strip():
                continue

            normalized_path = path.replace("\\", "/")
            retrieved_paths.add(normalized_path)

            code_sections.append(
                f"FILE: {normalized_path}\n"
                f"CODE:\n{content[:5000]}"
            )

        if not code_sections:
            return ImplementationPlan(
                summary="No usable code context was retrieved.",
                decision="INSUFFICIENT_CONTEXT",
                files_to_modify=[],
            )

        context = "\n\n---\n\n".join(code_sections)[:10000]

        prompt = f"""
You are a careful software engineer planning a minimal code change.

GITHUB ISSUE:
{problem}

EXPECTED BEHAVIOR:
{expected_behavior}

LIKELY COMPONENTS:
{json.dumps(likely_components)}

ACCEPTANCE CRITERIA:
{json.dumps(acceptance_criteria)}

RETRIEVED REPOSITORY CODE:
{context}

First decide whether a change is justified.

Choose exactly one decision:
1. CHANGE_REQUIRED:
   The retrieved code demonstrates a specific missing or incorrect behavior.
   Propose only the smallest justified change.
2. ALREADY_SUPPORTED:
   The retrieved code clearly demonstrates that the requested behavior
   is already implemented correctly.
3. INSUFFICIENT_CONTEXT:
   The retrieved code does not provide enough evidence to decide safely.

RULES:
- Do not assume a bug exists just because an issue reports it.
- Do not invent functions, APIs, or existing behavior.
- Only propose files explicitly listed in the retrieved code.
- Each file_path must exactly match a FILE path shown above.
- Do not propose unrelated refactoring.
- If a change is required, include at least one specific file change.
- If the behavior is already supported, return an empty files_to_modify list.
- If evidence is insufficient, return an empty files_to_modify list.
- Never use an empty plan to represent a required change.

Return ONLY valid JSON with this structure:
{{
  "summary": "short explanation",
  "decision": "CHANGE_REQUIRED",
  "files_to_modify": [
    {{
      "file_path": "exact retrieved file path",
      "change": "specific implementation change",
      "reason": "why the change is necessary"
    }}
  ]
}}

The decision value must be one of:
CHANGE_REQUIRED, ALREADY_SUPPORTED, INSUFFICIENT_CONTEXT.
"""

        try:
            response = ollama.chat(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )

            raw_content = response["message"]["content"]
            data = json.loads(raw_content)
            plan = ImplementationPlan.model_validate(data)

        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            print(f"[Planner] Invalid model response: {exc}")
            return ImplementationPlan(
                summary="Planner response was invalid; no changes proposed.",
                decision="INSUFFICIENT_CONTEXT",
                files_to_modify=[],
            )
        except Exception as exc:
            print(f"[Planner] Planning failed: {exc}")
            return ImplementationPlan(
                summary="Planning failed; no changes proposed.",
                decision="INSUFFICIENT_CONTEXT",
                files_to_modify=[],
            )

        safe_changes = []
        seen_paths = set()

        for change in plan.files_to_modify:
            raw_path = change.file_path.strip().replace("\\", "/")

            # Reject absolute paths, traversal, and Windows drive paths.
            path = PurePosixPath(raw_path)

            if (
                not raw_path
                or path.is_absolute()
                or ".." in path.parts
                or re.match(r"^[A-Za-z]:", raw_path)
            ):
                print(f"[Planner] Rejected unsafe path: {raw_path}")
                continue

            if raw_path not in retrieved_paths:
                print(f"[Planner] Rejected unretrieved path: {raw_path}")
                continue

            if raw_path in seen_paths:
                print(f"[Planner] Rejected duplicate path: {raw_path}")
                continue

            if not change.change.strip() or not change.reason.strip():
                print(f"[Planner] Rejected incomplete change: {raw_path}")
                continue

            seen_paths.add(raw_path)

            safe_changes.append(
                FileChange(
                    file_path=raw_path,
                    change=change.change.strip(),
                    reason=change.reason.strip(),
                )
            )

        if plan.decision == "CHANGE_REQUIRED":
            if not safe_changes:
                return ImplementationPlan(
                    summary=(
                        "The planner proposed a change, but no safe, "
                        "retrieved file changes remained after validation."
                    ),
                    decision="INSUFFICIENT_CONTEXT",
                    files_to_modify=[],
                )

            return ImplementationPlan(
                summary=plan.summary,
                decision="CHANGE_REQUIRED",
                files_to_modify=safe_changes,
            )

        # Do not accept proposed modifications under a non-actionable decision.
        if safe_changes:
            print(
                "[Planner] Non-actionable decision contained proposed changes; "
                "treating the result as insufficient context."
            )
            return ImplementationPlan(
                summary=(
                    "The planner returned contradictory decision and change data."
                ),
                decision="INSUFFICIENT_CONTEXT",
                files_to_modify=[],
            )

        return ImplementationPlan(
            summary=plan.summary,
            decision=plan.decision,
            files_to_modify=[],
        )