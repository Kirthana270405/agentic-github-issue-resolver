from urllib.parse import urlparse


def parse_issue_url(url: str):
    parsed = urlparse(url)

    parts = parsed.path.strip("/").split("/")

    if len(parts) != 4:
        raise ValueError("Invalid GitHub issue URL")

    if parts[2] != "issues":
        raise ValueError("URL is not a GitHub issue URL")

    owner = parts[0]
    repo = parts[1]

    try:
        issue_number = int(parts[3])
    except ValueError:
        raise ValueError("Invalid issue number")

    return owner, repo, issue_number