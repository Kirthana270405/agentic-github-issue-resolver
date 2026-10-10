
from pathlib import Path

from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.planner import PlannerAgent

from app.github.client import GitHubClient
from app.github.url_parser import parse_issue_url

from app.repository.file_discovery import FileDiscovery
from app.repository.chunker import CodeChunker
from app.repository.embedder import CodeEmbedder
from app.repository.retriever import CodeRetriever
from app.repository.issue_retriever import IssueRetriever


def main():
    # ============================================================
    # 1. GET ISSUE
    # ============================================================

    issue_url = "https://github.com/psf/requests/issues/1"

    owner, repo, issue_number = parse_issue_url(issue_url)

    github = GitHubClient()

    issue = github.get_issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
    )

    print(f"\nIssue #{issue.number}: {issue.title}")

    # ============================================================
    # 2. ANALYZE ISSUE
    # ============================================================

    analyzer = IssueAnalyzer()

    analysis = analyzer.analyze(
        title=issue.title,
        body=issue.body or "",
    )

    print("\nIssue analysis complete.")

    # ============================================================
    # 3. DISCOVER REPOSITORY
    # ============================================================

    repo_path = Path("workspace") / f"{owner}_{repo}"

    if not repo_path.is_dir():
        raise FileNotFoundError(
            f"Repository not found: {repo_path.resolve()}\n"
            "Clone the repository into the workspace directory first."
        )

    discovery = FileDiscovery()
    files = discovery.discover(repo_path)

    # ============================================================
    # 4. CHUNK REPOSITORY
    # ============================================================

    chunker = CodeChunker(chunk_size=80)
    chunks = chunker.chunk_files(files)

    print(f"Files: {len(files)}")
    print(f"Chunks: {len(chunks)}")

    if not chunks:
        print("No code chunks found. Cannot create an implementation plan.")
        return

    # ============================================================
    # 5. CREATE EMBEDDINGS
    # ============================================================

    embedder = CodeEmbedder()
    embeddings = embedder.embed_chunks(chunks)

    # ============================================================
    # 6. CREATE FAISS RETRIEVER
    # ============================================================

    retriever = CodeRetriever(
        chunks=chunks,
        embeddings=embeddings,
        embedder=embedder,
    )

    # ============================================================
    # 7. RETRIEVE RELEVANT CODE
    # ============================================================

    issue_retriever = IssueRetriever(retriever)

    results = issue_retriever.retrieve(
        analysis,
        top_k=5,
    )

    # ============================================================
    # 8. CONVERT RESULTS TO DICTIONARIES
    # ============================================================

    relevant_code = []

    for chunk, distance in results:
        relevant_code.append(
            {
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "content": chunk.content,
                "distance": distance,
            }
        )

    print(f"Relevant code chunks retrieved: {len(relevant_code)}")

    # ============================================================
    # 9. GENERATE IMPLEMENTATION PLAN
    # ============================================================

    planner = PlannerAgent()

    plan = planner.plan(
        problem=analysis.problem,
        expected_behavior=analysis.expected_behavior,
        likely_components=analysis.likely_components,
        acceptance_criteria=analysis.acceptance_criteria,
        relevant_code=relevant_code,
    )

    # ============================================================
    # 10. DISPLAY IMPLEMENTATION PLAN
    # ============================================================

    print("\n" + "=" * 70)
    print("IMPLEMENTATION PLAN")
    print("=" * 70)

    print("\nSummary:")
    print(plan.summary)

    print("\nFiles to modify:")

    if plan.files_to_modify:
        for change in plan.files_to_modify:
            print(f"\nFile: {change.file_path}")
            print(f"Change: {change.change}")
            print(f"Reason: {change.reason}")
    else:
        print("No files proposed for modification.")

    print("\nNote:")
    print(
        "The current ImplementationPlan schema contains "
        "'summary' and 'files_to_modify'."
    )
    print(
        "Test additions and validation steps are not included "
        "in the current schema."
    )


if __name__ == "__main__":
    main()
