from pathlib import Path

from app.agents.issue_analyzer import IssueAnalyzer
from app.github.client import GitHubClient
from app.github.url_parser import parse_issue_url

from app.repository.file_discovery import FileDiscovery
from app.repository.chunker import CodeChunker
from app.repository.embedder import CodeEmbedder
from app.repository.retriever import CodeRetriever
from app.repository.issue_retriever import IssueRetriever


# --------------------------------------------------
# 1. Get GitHub issue
# --------------------------------------------------

issue_url = "https://github.com/psf/requests/issues/1"

owner, repo, issue_number = parse_issue_url(
    issue_url
)

github = GitHubClient()

issue = github.get_issue(
    owner=owner,
    repo=repo,
    issue_number=issue_number
)

print(f"\nIssue #{issue.number}: {issue.title}")


# --------------------------------------------------
# 2. Analyze issue
# --------------------------------------------------

analyzer = IssueAnalyzer()

analysis = analyzer.analyze(
    title=issue.title,
    body=issue.body or ""
)

print("\nProblem:")
print(analysis.problem)

print("\nExpected behavior:")
print(analysis.expected_behavior)


# --------------------------------------------------
# 3. Discover repository files
# --------------------------------------------------

repo_path = Path(
    f"workspace/{owner}_{repo}"
)

discovery = FileDiscovery()

files = discovery.discover(
    repo_path
)


# --------------------------------------------------
# 4. Chunk repository
# --------------------------------------------------

chunker = CodeChunker(
    chunk_size=80
)

chunks = chunker.chunk_files(
    files
)

print(f"\nFiles: {len(files)}")
print(f"Chunks: {len(chunks)}")


# --------------------------------------------------
# 5. Generate embeddings
# --------------------------------------------------

embedder = CodeEmbedder()

embeddings = embedder.embed_chunks(
    chunks
)


# --------------------------------------------------
# 6. Build FAISS retriever
# --------------------------------------------------

retriever = CodeRetriever(
    chunks=chunks,
    embeddings=embeddings,
    embedder=embedder
)


# --------------------------------------------------
# 7. Retrieve code relevant to issue
# --------------------------------------------------

issue_retriever = IssueRetriever(
    retriever
)

results = issue_retriever.retrieve(
    analysis,
    top_k=5
)


# --------------------------------------------------
# 8. Display results
# --------------------------------------------------

print("\n" + "=" * 70)
print("RELEVANT CODE FOR ISSUE")
print("=" * 70)

for i, (chunk, distance) in enumerate(
    results,
    start=1
):

    print(f"\n--- RESULT {i} ---")

    print(
        f"File: {chunk.file_path}"
    )

    print(
        f"Lines: "
        f"{chunk.start_line}-{chunk.end_line}"
    )

    print(
        f"Distance: {distance:.4f}"
    )

    print("\nCode:")
    print(chunk.content[:1000])