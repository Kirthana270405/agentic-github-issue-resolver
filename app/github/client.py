
import requests
from typing import Optional
from pydantic import BaseModel

from app.config import GITHUB_TOKEN


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: Optional[str]
    state: str
    author: str
    url: str


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> GitHubIssue:
        """Fetch a GitHub issue by repository and issue number."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        return GitHubIssue(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            author=data["user"]["login"],
            url=data["html_url"],
        )

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        """Create a pull request from a pushed branch into the base branch."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"

        response = requests.post(
            url,
            headers=self.headers,
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()

        return {
            "number": data["number"],
            "url": data["html_url"],
            "state": data["state"],
        }
