from app.repository.manager import RepositoryManager


manager = RepositoryManager()

repo_path = manager.clone_repository(
    owner="psf",
    repo="requests"
)

print("\nRepository path:")
print(repo_path)