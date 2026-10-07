"""
GitHub Webhook Listener & Event Verification for debim Cloud.
Handles HMAC SHA-256 signature verification and payload parsing for push events,
identifying modifications to project.yaml or sheets/*.yaml manifests.
"""

import fnmatch
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field


def verify_github_signature(
    payload_bytes: bytes,
    signature_header: Optional[str],
    secret: str,
) -> bool:
    """
    Verify incoming GitHub webhook signature using HMAC SHA-256 (X-Hub-Signature-256).

    Args:
        payload_bytes: Raw HTTP request body bytes.
        signature_header: Content of X-Hub-Signature-256 header (e.g., 'sha256=...').
        secret: Webhook secret key configured in GitHub repository settings.

    Returns:
        True if signature is valid and matches secret, False otherwise.
    """
    if not signature_header or not secret:
        return False

    header = signature_header.strip()
    if not header.startswith("sha256="):
        return False

    expected_sig = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(header, expected_sig)


def is_manifest_or_sheet_file(filepath: str) -> bool:
    """
    Check if a file path corresponds to project.yaml or sheets/*.yaml.
    """
    normalized = filepath.replace("\\", "/").strip()
    # Direct project manifest match
    if normalized == "project.yaml" or normalized.endswith("/project.yaml"):
        return True

    # Sheet YAML files match
    if normalized.startswith("sheets/") and (normalized.endswith(".yaml") or normalized.endswith(".yml")):
        return True

    # Wildcard fnmatch fallbacks
    if fnmatch.fnmatch(normalized, "project.yaml") or fnmatch.fnmatch(normalized, "*/project.yaml"):
        return True
    if fnmatch.fnmatch(normalized, "sheets/*.yaml") or fnmatch.fnmatch(normalized, "sheets/**/*.yaml"):
        return True

    return False


class WebhookPushEvent(BaseModel):
    """Parsed representation of a GitHub push webhook event."""

    ref: str = ""
    head_commit_id: Optional[str] = None
    pusher_name: Optional[str] = None
    repository_owner: str = ""
    repository_name: str = ""
    repository_full_name: str = ""
    modified_files: List[str] = Field(default_factory=list)
    added_files: List[str] = Field(default_factory=list)
    removed_files: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    @property
    def branch(self) -> str:
        """Extract branch name from Git ref (e.g., 'refs/heads/main' -> 'main')."""
        if self.ref.startswith("refs/heads/"):
            return self.ref[len("refs/heads/") :]
        return self.ref

    @property
    def all_changed_files(self) -> List[str]:
        """Combine unique modified, added, and removed files in order."""
        seen: Set[str] = set()
        changed: List[str] = []
        for f in self.modified_files + self.added_files + self.removed_files:
            if f not in seen:
                seen.add(f)
                changed.append(f)
        return changed

    def has_manifest_or_sheet_changes(self) -> bool:
        """Return True if push event modifies, adds, or removes project.yaml or sheets/*.yaml."""
        return any(is_manifest_or_sheet_file(f) for f in self.all_changed_files)

    def get_changed_manifest_or_sheet_files(self) -> List[str]:
        """Filter changed files that match project.yaml or sheets/*.yaml."""
        return [f for f in self.all_changed_files if is_manifest_or_sheet_file(f)]


def parse_push_event(payload: Union[str, bytes, Dict[str, Any]]) -> WebhookPushEvent:
    """
    Parse incoming GitHub push webhook payload into WebhookPushEvent model.

    Args:
        payload: JSON string, bytes, or parsed dict from GitHub push event payload.

    Returns:
        WebhookPushEvent object with extracted metadata and changed files.
    """
    if isinstance(payload, (str, bytes)):
        data: Dict[str, Any] = json.loads(payload)
    elif isinstance(payload, dict):
        data = payload
    else:
        raise TypeError(f"Unsupported payload type: {type(payload)}")

    ref = data.get("ref", "")
    head_commit = data.get("head_commit") or {}
    head_commit_id = head_commit.get("id") or data.get("after")

    pusher = data.get("pusher") or {}
    pusher_name = pusher.get("name") or pusher.get("login")

    repo = data.get("repository") or {}
    repo_name = repo.get("name", "")
    repo_full_name = repo.get("full_name", "")

    owner_data = repo.get("owner") or {}
    if isinstance(owner_data, str):
        repo_owner = owner_data
    else:
        repo_owner = owner_data.get("login") or owner_data.get("name") or ""

    if not repo_owner and "/" in repo_full_name:
        repo_owner = repo_full_name.split("/")[0]

    modified: List[str] = []
    added: List[str] = []
    removed: List[str] = []

    # Collect changes from head_commit or all commits in payload
    commits = data.get("commits") or []
    if not commits and head_commit:
        commits = [head_commit]

    for commit in commits:
        if isinstance(commit, dict):
            modified.extend(commit.get("modified", []))
            added.extend(commit.get("added", []))
            removed.extend(commit.get("removed", []))

    return WebhookPushEvent(
        ref=ref,
        head_commit_id=head_commit_id,
        pusher_name=pusher_name,
        repository_owner=repo_owner,
        repository_name=repo_name,
        repository_full_name=repo_full_name,
        modified_files=list(dict.fromkeys(modified)),
        added_files=list(dict.fromkeys(added)),
        removed_files=list(dict.fromkeys(removed)),
        raw_payload=data,
    )


class WebhookHandler:
    """
    GitHub Webhook Handler for validating signatures and processing push events.
    """

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret

    def verify_signature(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str],
    ) -> bool:
        """Verify HMAC SHA-256 signature if secret is configured."""
        if self.secret is None:
            return True
        return verify_github_signature(payload_bytes, signature_header, self.secret)

    def handle(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str] = None,
    ) -> WebhookPushEvent:
        """
        Verify signature (if secret present) and parse push payload into WebhookPushEvent.

        Raises:
            ValueError: If signature verification fails or payload is invalid.
        """
        if self.secret is not None:
            if not self.verify_signature(payload_bytes, signature_header):
                raise ValueError("Invalid GitHub webhook signature")

        return parse_push_event(payload_bytes)
