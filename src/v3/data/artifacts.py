"""incoming/2026-10-24-v3-l1 的原件与 MANIFEST。"""
from __future__ import annotations

import gzip
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INCOMING = ROOT / "incoming" / "2026-10-24-v3-l1"
MANIFEST = INCOMING / "MANIFEST.csv"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save(rel: str, raw: bytes, *, url: str, note: str = "") -> dict:
    """原件落盘。超过 32KB 的正文同时写 gzip，MANIFEST 记未压缩字节的 SHA256。"""
    path = INCOMING / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(raw)
    stored = rel
    if len(raw) > 32_768 and not rel.endswith(".gz"):
        stored = rel + ".gz"
        gz = INCOMING / stored
        gz.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz, "wb") as f:
            f.write(raw)
        if path.exists() and path.is_file() and path.suffix != ".gz":
            path.unlink()
        file_sha = sha256_bytes(gz.read_bytes())
        nbytes = gz.stat().st_size
    else:
        path.write_bytes(raw)
        file_sha = digest
        nbytes = len(raw)
    row = {
        "path": stored,
        "sha256": digest,
        "file_sha256": file_sha,
        "bytes": len(raw),
        "file_bytes": nbytes,
        "url": url,
        "fetched_at": now(),
        "note": note,
    }
    _append(row)
    return row


def _append(row: dict) -> None:
    INCOMING.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    cols = ["path", "sha256", "file_sha256", "bytes", "file_bytes", "url", "fetched_at", "note"]
    with MANIFEST.open("a", encoding="utf-8") as f:
        if new:
            f.write(",".join(cols) + "\n")
        vals = []
        for c in cols:
            text = str(row.get(c, "")).replace('"', "'")
            if any(ch in text for ch in ",\n"):
                text = '"' + text + '"'
            vals.append(text)
        f.write(",".join(vals) + "\n")
