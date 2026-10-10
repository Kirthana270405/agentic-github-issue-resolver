from typing import List, Tuple

from app.agents.issue_analyzer import IssueAnalysis
from app.repository.chunker import CodeChunk
from app.repository.retriever import CodeRetriever


class IssueRetriever:

    def __init__(
        self,
        retriever: CodeRetriever
    ):
        self.retriever = retriever

    def build_query(
        self,
        analysis: IssueAnalysis
    ) -> str:

        components = ", ".join(
            analysis.likely_components
        )

        criteria = " ".join(
            analysis.acceptance_criteria
        )

        query = f"""
Problem:
{analysis.problem}

Expected behavior:
{analysis.expected_behavior}

Likely components:
{components}

Acceptance criteria:
{criteria}
"""

        return query.strip()

    def retrieve(
        self,
        analysis: IssueAnalysis,
        top_k: int = 5
    ) -> List[Tuple[CodeChunk, float]]:

        query = self.build_query(analysis)

        return self.retriever.search(
            query=query,
            top_k=top_k
        )