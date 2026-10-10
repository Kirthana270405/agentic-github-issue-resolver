from pathlib import Path

from app.repository.file_discovery import FileDiscovery


repo_path = Path("workspace/psf_requests")

discovery = FileDiscovery()

files = discovery.discover(repo_path)

print(f"Found {len(files)} source files\n")

for file in files[:30]:
    print(file)