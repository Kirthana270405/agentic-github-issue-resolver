
import json
import re

import ollama


class DebuggerAgent:
    def __init__(self):
        self.model = "qwen3:1.7b"

    def analyze(self, test_result: dict) -> dict:
        """Classify test failures and recommend a safe next action."""

        if test_result.get("success"):
            return {
                "category": "none",
                "root_cause": "Tests passed.",
                "suggested_fix": "",
                "retry_recommended": False,
            }

        if test_result.get("skipped"):
            return {
                "category": "unknown",
                "root_cause": test_result.get(
                    "stderr", "Tests were skipped."
                ),
                "suggested_fix": "",
                "retry_recommended": False,
            }

        output = (
            str(test_result.get("stdout", ""))
            + "\n"
            + str(test_result.get("stderr", ""))
        )[-12000:]

        # Detect common environment failures without relying on the LLM.
        environment_patterns = [
            (
                r"Missing dependencies for SOCKS support",
                "A SOCKS dependency is missing.",
                "Install the repository's appropriate SOCKS dependency "
                "in the active Python environment.",
            ),
            (
                r"No module named ['\"]?([^'\"\s]+)",
                "A required Python module is missing.",
                "Check the repository's dependency instructions and install "
                "the missing dependency in the active environment.",
            ),
            (
                r"FileNotFoundError|No such file or directory",
                "A file or test fixture could not be found.",
                "Check whether the expected test fixture exists and whether "
                "the test environment is configured correctly.",
            ),
            (
                r"SSLError|CERTIFICATE_VERIFY_FAILED",
                "A certificate or TLS configuration error occurred.",
                "Check the test certificates and TLS test configuration.",
            ),
        ]

        for pattern, root_cause, suggested_fix in environment_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return {
                    "category": "environment",
                    "root_cause": root_cause,
                    "suggested_fix": suggested_fix,
                    "retry_recommended": False,
                }

        prompt = f"""
You are debugging a Python repository.

Analyze the test failure using only the supplied evidence.

Return a JSON object containing:
- category: "environment", "code", or "unknown"
- root_cause: concise explanation
- suggested_fix: specific, conservative next step
- retry_recommended: boolean

Rules:
1. Do not invent files, code, or facts.
2. Do not recommend changing application code for environment failures.
3. Recommend a retry only if a specific code-related fix is reasonably
   supported by the evidence.
4. If uncertain, use category "unknown" and do not recommend a retry.
5. A test failure alone does not prove that the generated patch caused it.

Test command: {test_result.get("command", "Unknown")}
Exit code: {test_result.get("exit_code")}

Test output:
{output}
"""

        schema = {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["environment", "code", "unknown"],
                },
                "root_cause": {"type": "string"},
                "suggested_fix": {"type": "string"},
                "retry_recommended": {"type": "boolean"},
            },
            "required": [
                "category",
                "root_cause",
                "suggested_fix",
                "retry_recommended",
            ],
        }

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Be conservative. Base every diagnosis on "
                            "the supplied test output."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                format=schema,
                think=False,
                options={
                    "temperature": 0,
                    "num_predict": 800,
                },
            )

            content = response.get("message", {}).get("content", "")

            if not content or not content.strip():
                raise ValueError("Ollama returned empty content.")

            diagnosis = json.loads(content)

            required_fields = {
                "category",
                "root_cause",
                "suggested_fix",
                "retry_recommended",
            }

            if not isinstance(diagnosis, dict):
                raise ValueError("Diagnosis is not a JSON object.")

            if not required_fields.issubset(diagnosis):
                raise ValueError("Diagnosis is missing required fields.")

            if diagnosis["category"] not in {
                "environment",
                "code",
                "unknown",
            }:
                raise ValueError("Invalid diagnosis category.")

            if not isinstance(diagnosis["retry_recommended"], bool):
                raise ValueError("retry_recommended must be a boolean.")

            if diagnosis["category"] != "code":
                diagnosis["retry_recommended"] = False

            return diagnosis

        except Exception as exc:
            print(f"\n[Debugger] Analysis error: {exc}")

            return {
                "category": "unknown",
                "root_cause": (
                    f"Debug analysis failed: {type(exc).__name__}."
                ),
                "suggested_fix": "",
                "retry_recommended": False,
            }
