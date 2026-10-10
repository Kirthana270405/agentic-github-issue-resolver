from pathlib import Path

from app.repository.file_discovery import FileDiscovery
from app.repository.chunker import CodeChunker
from app.repository.embedder import CodeEmbedder
from app.repository.retriever import CodeRetriever


repo_path = Path("workspace/psf_requests")

# Discover files
discovery = FileDiscovery()

files = discovery.discover(repo_path)

# Chunk files
chunker = CodeChunker(chunk_size=80)

chunks = chunker.chunk_files(files)

# Generate embeddings
embedder = CodeEmbedder()

embeddings = embedder.embed_chunks(chunks)

# Build retriever
retriever = CodeRetriever(
    chunks=chunks,
    embeddings=embeddings,
    embedder=embedder
)

# Test query
query = "How are HTTP sessions handled?"

results = retriever.search(
    query=query,
    top_k=5
)

print("\n" + "=" * 70)
print("QUERY")
print("=" * 70)

print(query)

print("\n" + "=" * 70)
print("RETRIEVED CODE")
print("=" * 70)

for i, (chunk, distance) in enumerate(results, start=1):

    print(f"\n--- RESULT {i} ---")

    print(f"File: {chunk.file_path}")
    print(
        f"Lines: "
        f"{chunk.start_line}-{chunk.end_line}"
    )

    print(f"Distance: {distance:.4f}")

    print("\nCode:")
    print(chunk.content[:1000])