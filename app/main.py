from app.github.client import GitHubClient
from app.github.url_parser import parse_issue_url
from app.agents.issue_analyzer import IssueAnalyzer


def analyze_issue(url: str):

    owner, repo, issue_number = parse_issue_url(url)

    github = GitHubClient()

    issue = github.get_issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number
    )

    print("\n" + "=" * 70)
    print(f"ISSUE #{issue.number}: {issue.title}")
    print("=" * 70)

    print(f"Repository: {owner}/{repo}")
    print(f"State: {issue.state}")
    print(f"Author: {issue.author}")
    print(f"URL: {issue.url}")

    analyzer = IssueAnalyzer()

    analysis = analyzer.analyze(
        title=issue.title,
        body=issue.body or ""
    )

    print("\n--- AI ANALYSIS ---")

    print("\nProblem:")
    print(analysis.problem)

    print("\nExpected Behavior:")
    print(analysis.expected_behavior)

    print("\nLikely Components:")
    for component in analysis.likely_components:
        print(f"- {component}")

    print("\nTechnical Constraints:")
    for constraint in analysis.technical_constraints:
        print(f"- {constraint}")

    print("\nAcceptance Criteria:")
    for criterion in analysis.acceptance_criteria:
        print(f"- {criterion}")


def main():

    test_issues = [
    "https://github.com/psf/requests/issues/1",
    "https://github.com/psf/requests/issues/2",
    "https://github.com/psf/requests/issues/3"
]

    for url in test_issues:
        analyze_issue(url)


if __name__ == "__main__":
    main()