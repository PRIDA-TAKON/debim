"""
Tests for GitHub Webhook Handling and debim[bot] Auto-Committer Engine.
"""

import hashlib
import hmac
import json
import pytest

from debim.cloud import (
    CommitFile,
    CommitResult,
    DebimBotCommitter,
    DEFAULT_BOT_EMAIL,
    DEFAULT_BOT_NAME,
    DEFAULT_COMMIT_MESSAGE,
    WebhookHandler,
    WebhookPushEvent,
    is_manifest_or_sheet_file,
    parse_push_event,
    verify_github_signature,
)


# --- Helper Mock HTTP Client for GitHub API ---
class MockGitHubHttpClient:
    def __init__(self):
        self.file_shas = {}
        self.committed_payloads = []
        self.should_fail_get = False
        self.should_fail_put = False
        self.put_status = 200
        self.put_error_message = "Bad Request"

    def get(self, url, headers=None):
        if self.should_fail_get:
            return MockResponse(404, {"message": "Not Found"})

        # Extract file path from URL
        for path, sha in self.file_shas.items():
            if f"/contents/{path}" in url:
                return MockResponse(200, {"sha": sha, "type": "file", "path": path})

        return MockResponse(404, {"message": "Not Found"})

    def put(self, url, headers=None, json=None):
        if self.should_fail_put:
            return MockResponse(self.put_status, {"message": self.put_error_message})

        self.committed_payloads.append({"url": url, "headers": headers, "json": json})
        commit_sha = f"mock_commit_sha_{len(self.committed_payloads)}"
        path = url.split("/contents/")[-1] if "/contents/" in url else "file"
        self.file_shas[path] = f"sha_for_{path}"

        return MockResponse(
            200,
            {
                "content": {"name": path, "path": path, "sha": self.file_shas[path]},
                "commit": {"sha": commit_sha, "message": json.get("message") if json else ""},
            },
        )


class MockResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self.status = status_code
        self.data = data

    def json(self):
        return self.data


# --- 1. Signature Verification Tests ---
def test_verify_github_signature_valid():
    secret = "super_secret_key"
    payload = b'{"ref": "refs/heads/main", "repository": {"name": "test-repo"}}'
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert verify_github_signature(payload, sig, secret) is True


def test_verify_github_signature_invalid():
    secret = "super_secret_key"
    payload = b'{"ref": "refs/heads/main"}'
    wrong_sig = "sha256=1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    assert verify_github_signature(payload, wrong_sig, secret) is False


def test_verify_github_signature_missing_header_or_secret():
    payload = b'{"ref": "refs/heads/main"}'
    sig = "sha256=abcd"

    assert verify_github_signature(payload, None, "secret") is False
    assert verify_github_signature(payload, sig, "") is False
    assert verify_github_signature(payload, "invalid_prefix_sig", "secret") is False


# --- 2. Manifest and Sheet File Path Detection Tests ---
@pytest.mark.parametrize(
    "filepath, expected",
    [
        ("project.yaml", True),
        ("./project.yaml", True),
        ("subfolder/project.yaml", True),
        ("sheets/ground_floor.yaml", True),
        ("sheets/level2.yml", True),
        ("sheets/nested/sheet1.yaml", True),
        ("README.md", False),
        ("src/debim/schema.py", False),
        ("other_dir/sheet.yaml", False),
    ],
)
def test_is_manifest_or_sheet_file(filepath, expected):
    assert is_manifest_or_sheet_file(filepath) == expected


# --- 3. Webhook Push Event Parsing Tests ---
def test_parse_push_event():
    raw_payload = {
        "ref": "refs/heads/main",
        "after": "head_commit_sha_123",
        "pusher": {"name": "jules-bot"},
        "repository": {
            "name": "bim-project",
            "full_name": "acme/bim-project",
            "owner": {"login": "acme"},
        },
        "commits": [
            {
                "id": "commit1",
                "modified": ["project.yaml", "README.md"],
                "added": ["sheets/first_floor.yaml"],
                "removed": [],
            },
            {
                "id": "commit2",
                "modified": ["sheets/second_floor.yaml"],
                "added": [],
                "removed": ["old_file.txt"],
            },
        ],
    }

    event = parse_push_event(raw_payload)

    assert event.branch == "main"
    assert event.head_commit_id == "head_commit_sha_123"
    assert event.pusher_name == "jules-bot"
    assert event.repository_owner == "acme"
    assert event.repository_name == "bim-project"
    assert event.repository_full_name == "acme/bim-project"

    assert "project.yaml" in event.modified_files
    assert "sheets/first_floor.yaml" in event.added_files
    assert "old_file.txt" in event.removed_files

    assert event.has_manifest_or_sheet_changes() is True
    manifest_changes = event.get_changed_manifest_or_sheet_files()
    assert "project.yaml" in manifest_changes
    assert "sheets/first_floor.yaml" in manifest_changes
    assert "sheets/second_floor.yaml" in manifest_changes
    assert "README.md" not in manifest_changes


def test_parse_push_event_no_manifest_changes():
    raw_payload = {
        "ref": "refs/heads/feature",
        "repository": {"name": "test-repo", "owner": "test-owner"},
        "head_commit": {
            "id": "commit99",
            "modified": ["src/main.py", "docs/index.html"],
            "added": [],
            "removed": [],
        },
    }

    event = parse_push_event(raw_payload)
    assert event.branch == "feature"
    assert event.has_manifest_or_sheet_changes() is False
    assert event.get_changed_manifest_or_sheet_files() == []


def test_webhook_handler_integration():
    secret = "my_webhook_secret"
    payload = json.dumps({
        "ref": "refs/heads/dev",
        "repository": {"name": "demo", "owner": "org"},
        "head_commit": {"id": "c1", "modified": ["project.yaml"]},
    }).encode("utf-8")

    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    handler = WebhookHandler(secret=secret)
    event = handler.handle(payload, signature_header=sig)

    assert event.branch == "dev"
    assert event.has_manifest_or_sheet_changes() is True

    # Invalid signature should raise ValueError
    with pytest.raises(ValueError, match="Invalid GitHub webhook signature"):
        handler.handle(payload, signature_header="sha256=invalid")


# --- 4. DebimBotCommitter Auto-Committer Tests ---
def test_bot_committer_formatting():
    committer = DebimBotCommitter()
    assert committer.format_commit_message() == DEFAULT_COMMIT_MESSAGE
    assert committer.format_commit_message("  ") == DEFAULT_COMMIT_MESSAGE
    custom_msg = "feat(bim): update walls in storey 1"
    assert committer.format_commit_message(custom_msg) == custom_msg


def test_bot_committer_single_file_commit_success():
    client = MockGitHubHttpClient()
    committer = DebimBotCommitter(token="ghp_fake_token", http_client=client)

    file_to_commit = CommitFile(path="model.ifc", content="ISO-10303-21; ...")
    res = committer.commit_file(
        owner="acme",
        repo="bim-project",
        branch="main",
        file=file_to_commit,
    )

    assert res.success is True
    assert res.owner == "acme"
    assert res.repo == "bim-project"
    assert res.branch == "main"
    assert res.files_committed == ["model.ifc"]
    assert res.commit_sha == "mock_commit_sha_1"
    assert res.message == DEFAULT_COMMIT_MESSAGE

    assert len(client.committed_payloads) == 1
    p = client.committed_payloads[0]
    assert p["json"]["committer"]["name"] == DEFAULT_BOT_NAME
    assert p["json"]["committer"]["email"] == DEFAULT_BOT_EMAIL
    assert "content" in p["json"]


def test_bot_committer_existing_file_sha_fetch():
    client = MockGitHubHttpClient()
    client.file_shas["project.yaml"] = "existing_sha_abc123"
    committer = DebimBotCommitter(token="ghp_fake_token", http_client=client)

    file_to_commit = CommitFile(path="project.yaml", content="project:\n  id: P100\n")
    res = committer.commit_file(
        owner="acme",
        repo="bim-project",
        branch="main",
        file=file_to_commit,
    )

    assert res.success is True
    assert client.committed_payloads[0]["json"]["sha"] == "existing_sha_abc123"


def test_bot_committer_multi_file_commits():
    client = MockGitHubHttpClient()
    committer = DebimBotCommitter(token="ghp_fake_token", http_client=client)

    files = [
        CommitFile(path="viewer.html", content="<html>Viewer</html>"),
        CommitFile(path="boq.csv", content="Item,Cost\nConcrete,100"),
    ]

    res = committer.commit_files(
        owner="acme",
        repo="bim-project",
        branch="main",
        files=files,
        commit_message="chore(debim): publish compile artifacts",
    )

    assert res.success is True
    assert res.files_committed == ["viewer.html", "boq.csv"]
    assert res.message == "chore(debim): publish compile artifacts"
    assert len(client.committed_payloads) == 2


def test_bot_committer_api_failure_handling():
    client = MockGitHubHttpClient()
    client.should_fail_put = True
    client.put_status = 403
    client.put_error_message = "Resource not accessible by integration"

    committer = DebimBotCommitter(token="ghp_fake_token", http_client=client)
    file_to_commit = CommitFile(path="model.ifc", content="data")

    res = committer.commit_file(
        owner="acme",
        repo="bim-project",
        branch="main",
        file=file_to_commit,
    )

    assert res.success is False
    assert "Resource not accessible" in res.error
