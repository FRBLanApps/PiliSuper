#!/usr/bin/env python3
"""Publish CI build artifacts and build metadata to Telegram."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

ARTIFACT_SUFFIXES = (
    ".apk",
    ".ipa",
    ".dmg",
    ".zip",
    ".exe",
    ".tar.gz",
    ".deb",
    ".rpm",
    ".appimage",
    ".pkg.tar.zst",
)
DEFAULT_MAX_FILE_MIB = 49


@dataclass(frozen=True)
class Artifact:
    path: Path
    name: str
    size: int


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_artifacts(output_dir: Path) -> list[Artifact]:
    if not output_dir.is_dir():
        raise SystemExit(f"artifact directory does not exist: {output_dir}")

    artifacts: list[Artifact] = []
    seen: set[tuple[str, int]] = set()
    for path in sorted(output_dir.rglob("*"), key=lambda item: item.name.lower()):
        if not path.is_file() or not path.name.lower().endswith(ARTIFACT_SUFFIXES):
            continue
        size = path.stat().st_size
        identity = (file_digest(path), size)
        if identity in seen:
            continue
        seen.add(identity)
        artifacts.append(Artifact(path=path, name=path.name, size=size))

    if not artifacts:
        raise SystemExit(f"no distributable artifacts found in {output_dir}")
    return artifacts


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def format_size(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def build_message(
    *,
    label: str,
    repository: str,
    branch: str,
    commit_sha: str,
    commit_message: str,
    run_url: str,
    artifacts: list[Artifact],
    skipped: list[Artifact],
    release_tag: str,
) -> str:
    commit_url = f"https://github.com/{repository}/commit/{commit_sha}"
    artifact_lines = "\n".join(
        f"• <code>{html.escape(item.name)}</code> ({format_size(item.size)})"
        for item in artifacts
    )
    skipped_section = ""
    if skipped:
        skipped_names = ", ".join(html.escape(item.name) for item in skipped)
        skipped_section = (
            "\n\n⚠️ <b>仅保留 Actions 下载:</b> "
            f"{skipped_names}（超过 Telegram 上传限制）"
        )

    release_section = (
        f"📣 <b>这是一个 Release:</b> <code>{html.escape(release_tag)}</code>\n\n"
        if release_tag
        else ""
    )
    message = (
        f"📦 <b>{html.escape(label)}</b>\n\n{release_section}"
        f"🌿 <b>分支:</b> <code>{html.escape(branch)}</code>\n"
        f"📝 <b>提交:</b> <a href=\"{html.escape(commit_url)}\">"
        f"{html.escape(commit_sha[:9])}</a>\n"
        f"<pre>{html.escape(truncate(commit_message, 600))}</pre>\n"
        f"📚 <b>产物:</b> {len(artifacts)}\n{artifact_lines}"
        f"{skipped_section}\n\n"
        f"🔗 <a href=\"{html.escape(run_url)}\">GitHub Actions 下载与日志</a>"
    )
    return truncate(message, 4096)


class TelegramClient:
    def __init__(
        self,
        token: str,
        chat_id: str,
        topic_id: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.timeout = timeout

    def _response_result(self, response: bytes) -> object:
        payload = json.loads(response)
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram API request failed"))
        return payload["result"]

    def send_message(self, text: str) -> int:
        fields = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
        if self.topic_id:
            fields["message_thread_id"] = self.topic_id
        request = urllib.request.Request(
            f"{self.base_url}/sendMessage",
            data=urllib.parse.urlencode(fields).encode(),
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = self._response_result(response.read())
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise RuntimeError("Telegram did not return a message ID")
        return result["message_id"]

    def pin_message(self, message_id: int) -> None:
        fields = {
            "chat_id": self.chat_id,
            "message_id": str(message_id),
            "disable_notification": "true",
        }
        request = urllib.request.Request(
            f"{self.base_url}/pinChatMessage",
            data=urllib.parse.urlencode(fields).encode(),
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            self._response_result(response.read())

    def send_document(self, artifact: Artifact) -> None:
        boundary = f"PiliSuper-{uuid.uuid4().hex}"
        fields = {"chat_id": self.chat_id}
        if self.topic_id:
            fields["message_thread_id"] = self.topic_id

        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            )
        content_type = mimetypes.guess_type(artifact.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                'Content-Disposition: form-data; name="document"; '
                f'filename="{artifact.name}"\r\nContent-Type: {content_type}\r\n\r\n'
            ).encode()
        )
        body.extend(artifact.path.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        request = urllib.request.Request(
            f"{self.base_url}/sendDocument",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            self._response_result(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="notify-output", type=Path)
    parser.add_argument("--label", default="PiliSuper CI 构建产物")
    parser.add_argument("--topic-id")
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--max-file-mib", type=int, default=DEFAULT_MAX_FILE_MIB)
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram credentials are not configured; skipping notification.")
        return 0

    topic_id = args.topic_id or os.environ.get("TELEGRAM_TOPIC_ID", "").strip() or None
    artifacts = find_artifacts(args.output)
    max_bytes = args.max_file_mib * 1024 * 1024
    uploadable = [item for item in artifacts if item.size <= max_bytes]
    skipped = [item for item in artifacts if item.size > max_bytes]

    repository = os.environ.get("GITHUB_REPOSITORY", "FRBLanApps/PiliSuper")
    branch = os.environ.get("GITHUB_REF_NAME", "") or git_output(
        "rev-parse", "--abbrev-ref", "HEAD"
    )
    commit_sha = (
        os.environ.get("SOURCE_SHA", "")
        or os.environ.get("GITHUB_SHA", "")
        or git_output("rev-parse", "HEAD")
    )
    commit_message = git_output("log", "-1", "--pretty=%B") or "No commit message"
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"

    client = TelegramClient(token, chat_id, topic_id)
    message = build_message(
        label=args.label,
        repository=repository,
        branch=branch,
        commit_sha=commit_sha,
        commit_message=commit_message,
        run_url=run_url,
        artifacts=artifacts,
        skipped=skipped,
        release_tag=args.release_tag,
    )
    try:
        message_id = client.send_message(message)
        if args.release_tag:
            client.pin_message(message_id)
        for artifact in uploadable:
            print(f"Sending {artifact.name} ({format_size(artifact.size)})")
            client.send_document(artifact)
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"Telegram notification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
