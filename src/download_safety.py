"""Size and path guards for remotely supplied playback assets."""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
from typing import Any


async def read_response_limited(response: Any, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Download exceeds {max_bytes} byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def safe_download_path(directory: str, filename: str, *, source: str) -> str:
    base = Path(directory).resolve()
    safe_name = Path(filename.replace("\\", "/")).name.strip()
    if safe_name in {"", ".", ".."}:
        raise ValueError("Remote response supplied an invalid filename")
    digest = sha1(source.encode("utf-8")).hexdigest()[:12]
    destination = (base / f"{digest}_{safe_name}").resolve()
    if not destination.is_relative_to(base):
        raise ValueError("Download path escapes the temporary directory")
    return str(destination)


def resolve_existing_path(root: str, relative_path: str) -> str | None:
    base = Path(root).resolve()
    candidate = (base / relative_path).resolve()
    if not candidate.is_relative_to(base) or not candidate.exists():
        return None
    return str(candidate)
