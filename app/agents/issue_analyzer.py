
import json
import re
from typing import List

import ollama
from pydantic import BaseModel, Field, ValidationError


class IssueAnalysis(BaseModel):
    problem: str
    expected_behavior: str
    likely_components: List[str] = Field(default_factory=list)
    technical_constraints: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class IssueAnalyzer:
    def __init__(self):
        self.model = "qwen3:1.7b"

    def analyze(self, title: str, body: str) -> IssueAnalysis:
        """Analyze a GitHub issue using structured model output."""

        title = (title or "").strip()
        body = (body or "").strip()

        if not title and not body:
            raise ValueError(
                "Cannot analyze an issue without a title or description."
            )

        # Do not let the model invent requirements when the description
        # contains no useful information.
        if not body:
            return IssueAnalysis(
                problem=f"Issue title: {title}. The issue has no description.",
                expected_behavior=(
                    "The expected behavior cannot be determined "
                    "reliably from the title alone."
                ),
                likely_components=[],
                technical_constraints=[
                    "Do not assume requirements that are not stated."
                ],
                acceptance_criteria=[
                    "Obtain sufficient issue details before implementing "
                    "a behavior-changing patch."
                ],
            )

        prompt = f"""
You are a careful software engineering issue-analysis agent.

Analyze the GitHub issue below. Use only information supported by
the title and description.

ISSUE TITLE:
{title}

ISSUE DESCRIPTION:
{body}

Return these fields:
- problem: the actual problem or requested change.
- expected_behavior: the behavior required after resolution.
- likely_components: relevant software components, if identifiable.
- technical_constraints: existing behavior or requirements to preserve.
- acceptance_criteria: concrete conditions for success.

Rules:
1. Do not invent requirements, files, APIs, or implementation details.
2. Distinguish explicit requirements from uncertainty.
3. Keep the analysis concise and specific.
4. If the issue is ambiguous, explain what is unclear.
5. Do not propose a fix unsupported by the issue.
6. Return JSON only, matching the supplied schema.
"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                format=IssueAnalysis.model_json_schema(),
                think=False,
                options={
                    "temperature": 0,
                    "num_predict": 1200,
                    "repeat_penalty": 1.1,
                },
            )
        except Exception as exc:
            raise RuntimeError(
                f"Issue analysis failed while calling Ollama: {exc}"
            ) from exc

        message = response.get("message", {})
        content = message.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Issue analyzer returned empty output.")

        content = content.strip()

        # Handle accidental Markdown fences if the model returns them.
        content = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"\s*```\s*$", "", content).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Issue analyzer returned invalid JSON: {exc}"
            ) from exc

        try:
            analysis = IssueAnalysis.model_validate(data)
        except ValidationError as exc:
            raise ValueError(
                f"Issue analyzer returned an invalid structure: {exc}"
            ) from exc

        # Reject empty or uninformative core fields instead of silently
        # passing them to retrieval and planning.
        if not analysis.problem.strip():
            raise ValueError("Issue analysis produced an empty problem.")

        if not analysis.expected_behavior.strip():
            raise ValueError(
                "Issue analysis produced an empty expected behavior."
            )

        return analysis
