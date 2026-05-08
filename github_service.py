"""GitHub operations: append a timestamp line to README.md on a configured branch."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from github import Auth, Github, GithubException

logger = logging.getLogger(__name__)


def _config() -> tuple[str | None, str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("REPO_NAME", "PoliteCoder97/politecoderrepo")
    branch = os.environ.get("BRANCH_NAME", "develop")
    return token, repo_name, branch


def append_readme_and_push() -> dict:
    """
    Append an ISO timestamp line to README.md and commit to the configured branch.

    Returns a dict with ok: bool and optional error / timestamp fields.
    Does not raise for GitHub or network failures so callers can stay up.
    """
    token, repo_name, branch = _config()
    if not token:
        logger.error("GITHUB_TOKEN is not set")
        return {"ok": False, "error": "GITHUB_TOKEN is not set"}

    timestamp = datetime.now(timezone.utc).isoformat()
    new_line = f"\n<!-- auto-commit: {timestamp} -->\n"
    readme_path = "README.md"

    try:
        g = Github(auth=Auth.Token(token))
        repo = g.get_repo(repo_name)

        try:
            contents = repo.get_contents(readme_path, ref=branch)
            body = contents.decoded_content.decode("utf-8")
            updated = body + new_line
            repo.update_file(
                readme_path,
                f"chore: automated README update {timestamp}",
                updated,
                contents.sha,
                branch=branch,
            )
        except GithubException as ge:
            if ge.status == 404:
                repo.create_file(
                    readme_path,
                    f"chore: init README with automated update {timestamp}",
                    f"# {repo.name}\n{new_line}",
                    branch=branch,
                )
            else:
                raise

        return {"ok": True, "timestamp": timestamp, "branch": branch, "repo": repo_name}

    except GithubException as e:
        logger.exception("GitHub API error (status=%s)", getattr(e, "status", None))
        return {
            "ok": False,
            "error": str(e),
            "status": getattr(e, "status", None),
        }
    except OSError as e:
        logger.exception("Network or I/O error talking to GitHub")
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("Unexpected error during GitHub update")
        return {"ok": False, "error": str(e)}
