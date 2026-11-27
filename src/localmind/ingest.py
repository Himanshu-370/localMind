"""Discovery, parsing and provenance. Never modifies source files."""
from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

TEXT_EXTS = {".md", ".markdown", ".txt", ".rst"}
CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".h",
             ".cpp", ".sh", ".json", ".yaml", ".yml", ".toml"}
SUPPORTED = TEXT_EXTS | CODE_EXTS | {".pdf"}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist",
             "build", "target", "site-packages", ".tox"}
SKIP_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore", ".crt"}
SKIP_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", ".netrc"}


@dataclass
class Doc:
    doc_id: str
    path: str  # absolute, canonical
    text: str


@dataclass
class ScanResult:
    docs: list[Doc] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    discovered: int = 0


def doc_id_for(path: str) -> str:
    return "doc-" + hashlib.sha1(path.encode()).hexdigest()[:16]


def canonical_roots(roots: list[str]) -> list[Path]:
    """Resolve, dedupe, drop roots nested inside another root."""
    resolved = sorted({Path(r).expanduser().resolve() for r in roots})
    out: list[Path] = []
    for r in resolved:
        if not any(r == o or o in r.parents for o in out):
            out.append(r)
    return out


def _skip_reason(name: str) -> str | None:
    low = name.lower()
    if low.startswith("."):
        return "hidden"
    if low == ".env" or low.startswith(".env.") or low in SKIP_NAMES or Path(low).stem in SKIP_NAMES:
        return "credential file"
    if Path(low).suffix in SKIP_SUFFIXES or low.startswith("id_rsa"):
        return "credential file"
    return None


def parse_file(path: Path, max_bytes: int) -> str:
    """Return text or raise ValueError with an actionable reason."""
    if path.stat().st_size > max_bytes:
        raise ValueError(f"larger than {max_bytes // 1024 // 1024} MB limit")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        text = "\n\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        if not text.strip():
            raise ValueError("PDF has no text layer (scanned PDFs unsupported)")
        return text
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("binary content")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("not valid UTF-8")
    if not text.strip():
        raise ValueError("empty file")
    return text


def scan(roots: list[str], exclude: Sequence[Path] = (), max_mb: int = 5,
         on_file=None) -> ScanResult:
    """Walk approved roots only. `exclude` = dirs never scanned (vault, storage)."""
    res = ScanResult()
    excl = [Path(e).resolve() for e in exclude]
    seen: set[str] = set()
    for root in canonical_roots(roots):
        if not root.is_dir():
            res.failed.append((str(root), "root missing or not a directory"))
            continue
        for dirpath, dirs, files in os.walk(root, followlinks=False):
            here = Path(dirpath)
            keep = []
            for d in sorted(dirs):
                p = here / d
                if p.is_symlink() or d.startswith(".") or d in SKIP_DIRS:
                    continue
                if any(p.resolve() == e for e in excl):
                    continue
                keep.append(d)
            dirs[:] = keep
            for name in sorted(files):
                p = here / name
                if Path(name).suffix.lower() not in SUPPORTED:
                    continue  # unsupported types are ignored, not counted
                res.discovered += 1
                if p.is_symlink():
                    res.skipped.append((str(p), "symlink"))
                    continue
                reason = _skip_reason(name)
                if reason:
                    res.skipped.append((str(p), reason))
                    continue
                real = p.resolve()
                if root not in real.parents or str(real) in seen:
                    res.skipped.append((str(p), "outside root or duplicate"))
                    continue
                seen.add(str(real))
                try:
                    text = parse_file(real, max_mb * 1024 * 1024)
                except ValueError as e:
                    res.skipped.append((str(real), str(e)))
                    continue
                except Exception as e:  # corrupt PDF etc.: keep going
                    res.failed.append((str(real), f"{type(e).__name__}: {e}"))
                    continue
                res.docs.append(Doc(doc_id_for(str(real)), str(real), text))
                if on_file:
                    on_file(res)
    return res
