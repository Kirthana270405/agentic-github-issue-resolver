from pathlib import Path

from app.repository.file_discovery import FileDiscovery
from app.repository.chunker import CodeChunker


repo_path = Path("workspace/psf_requests")

discovery = FileDiscovery()

files = discovery.discover(repo_path)

chunker = CodeChunker(chunk_size=80)

chunks = chunker.chunk_files(files)

print(f"Files discovered: {len(files)}")
print(f"Code chunks created: {len(chunks)}")

print("\n--- SAMPLE CHUNK ---")

if chunks:
    chunk = chunks[0]

    print(f"File: {chunk.file_path}")
    print(f"Lines: {chunk.start_line}-{chunk.end_line}")
    print()
    print(chunk.content)