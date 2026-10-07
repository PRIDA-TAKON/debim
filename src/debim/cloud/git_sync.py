"""
debim[bot] Auto-Committer Engine for GitHub Synchronization.
Provides helpers and API wrapper to commit compiled artifacts or AI-modified YAML manifests
back to target repository branches via GitHub REST API.
"""

import base64
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

DEFAULT_COMMIT_MESSAGE = "chore(debim): update compiled artifacts [skip ci]"
DEFAULT_BOT_NAME = "debim[bot]"
DEFAULT_BOT_EMAIL = "12345678+debim[bot]@users.noreply.github.com"


class CommitFile(BaseModel):
    """File to be committed to GitHub repository."""

    path: str
    content: Union[str, bytes]
    message: Optional[str] = None

    def get_content_bytes(self) -> bytes:
        if isinstance(self.content, bytes):
            return self.content
        return self.content.encode("utf-8")

    def get_base64_content(self) -> str:
        return base64.b64encode(self.get_content_bytes()).decode("utf-8")


class CommitResult(BaseModel):
    """Result of automated commit operation."""

    success: bool
    owner: str = ""
    repo: str = ""
    branch: str = ""
    commit_sha: Optional[str] = None
    files_committed: List[str] = Field(default_factory=list)
    message: str = ""
    error: Optional[str] = None


class DebimBotCommitter:
    """
    Automated Git committer (debim[bot]) utilizing GitHub REST API.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        bot_name: str = DEFAULT_BOT_NAME,
        bot_email: str = DEFAULT_BOT_EMAIL,
        api_base_url: str = "https://api.github.com",
        http_client: Optional[Any] = None,
    ):
        self.token = token
        self.bot_name = bot_name
        self.bot_email = bot_email
        self.api_base_url = api_base_url.rstrip("/")
        self.http_client = http_client

    def format_commit_message(self, message: Optional[str] = None) -> str:
        """Format standardized commit message with [skip ci] tag."""
        if not message or not message.strip():
            return DEFAULT_COMMIT_MESSAGE
        return message.strip()

    def _get_file_sha(self, owner: str, repo: str, path: str, branch: str) -> Optional[str]:
        """Fetch current file SHA if it exists in repository branch."""
        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "debim-bot",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            if self.http_client and hasattr(self.http_client, "get"):
                resp = self.http_client.get(url, headers=headers)
                if getattr(resp, "status_code", 0) == 200 or getattr(resp, "status", 0) == 200:
                    data = resp.json() if callable(getattr(resp, "json", None)) else resp.data
                    return data.get("sha") if isinstance(data, dict) else None
                return None

            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("sha")
        except Exception:
            return None
        return None

    def commit_file(
        self,
        owner: str,
        repo: str,
        branch: str,
        file: CommitFile,
        commit_message: Optional[str] = None,
    ) -> CommitResult:
        """
        Commit a single file to a GitHub repository branch via Contents API.
        """
        formatted_message = self.format_commit_message(commit_message or file.message)
        sha = self._get_file_sha(owner, repo, file.path, branch)

        url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{file.path}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "debim-bot",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload: Dict[str, Any] = {
            "message": formatted_message,
            "content": file.get_base64_content(),
            "branch": branch,
            "committer": {
                "name": self.bot_name,
                "email": self.bot_email,
            },
        }
        if sha:
            payload["sha"] = sha

        try:
            payload_bytes = json.dumps(payload).encode("utf-8")

            if self.http_client and hasattr(self.http_client, "put"):
                resp = self.http_client.put(url, headers=headers, json=payload)
                status_code = getattr(resp, "status_code", getattr(resp, "status", 0))
                data = resp.json() if callable(getattr(resp, "json", None)) else getattr(resp, "data", {})
                if status_code in (200, 201):
                    commit_sha = data.get("commit", {}).get("sha") if isinstance(data, dict) else None
                    return CommitResult(
                        success=True,
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        commit_sha=commit_sha,
                        files_committed=[file.path],
                        message=formatted_message,
                    )
                else:
                    err_msg = data.get("message") if isinstance(data, dict) else f"HTTP {status_code}"
                    return CommitResult(
                        success=False,
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        message=formatted_message,
                        error=f"GitHub API Error: {err_msg}",
                    )

            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="PUT")
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 201):
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    commit_sha = resp_data.get("commit", {}).get("sha")
                    return CommitResult(
                        success=True,
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        commit_sha=commit_sha,
                        files_committed=[file.path],
                        message=formatted_message,
                    )
                else:
                    return CommitResult(
                        success=False,
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        message=formatted_message,
                        error=f"GitHub API HTTP status: {resp.status}",
                    )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
            return CommitResult(
                success=False,
                owner=owner,
                repo=repo,
                branch=branch,
                message=formatted_message,
                error=f"HTTP {e.code}: {error_body}",
            )
        except Exception as e:
            return CommitResult(
                success=False,
                owner=owner,
                repo=repo,
                branch=branch,
                message=formatted_message,
                error=str(e),
            )

    def commit_files(
        self,
        owner: str,
        repo: str,
        branch: str,
        files: List[CommitFile],
        commit_message: Optional[str] = None,
    ) -> CommitResult:
        """
        Commit multiple files to GitHub repository.
        Iterates over files and commits them individually or in sequence.
        """
        if not files:
            return CommitResult(
                success=True,
                owner=owner,
                repo=repo,
                branch=branch,
                message=self.format_commit_message(commit_message),
                files_committed=[],
            )

        committed_paths: List[str] = []
        last_sha: Optional[str] = None
        formatted_message = self.format_commit_message(commit_message)

        for f in files:
            res = self.commit_file(
                owner=owner,
                repo=repo,
                branch=branch,
                file=f,
                commit_message=commit_message,
            )
            if not res.success:
                return CommitResult(
                    success=False,
                    owner=owner,
                    repo=repo,
                    branch=branch,
                    commit_sha=last_sha,
                    files_committed=committed_paths,
                    message=formatted_message,
                    error=res.error,
                )
            committed_paths.extend(res.files_committed)
            if res.commit_sha:
                last_sha = res.commit_sha

        return CommitResult(
            success=True,
            owner=owner,
            repo=repo,
            branch=branch,
            commit_sha=last_sha,
            files_committed=committed_paths,
            message=formatted_message,
        )
