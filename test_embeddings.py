from pathlib import Path

from app.repository.file_discovery import FileDiscovery
from app.repository.chunker import CodeChunker
from app.repository.embedder import CodeEmbedder


repo_path = Path("workspace/psf_requests")

discovery = FileDiscovery()
files = discovery.discover(repo_path)

chunker = CodeChunker(chunk_size=80)
chunks = chunker.chunk_files(files)

print(f"Files: {len(files)}")
print(f"Chunks: {len(chunks)}")

embedder = CodeEmbedder()

embeddings = embedder.embed_chunks(chunks)

print("\nEmbedding shape:")
print(embeddings.shape)

print("\nFirst embedding:")
print(embeddings[0][:10])