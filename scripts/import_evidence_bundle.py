#!/usr/bin/env python3
"""Decode base64 evidence bundle or extract trajectories tarball.

Usage:
  python scripts/import_evidence_bundle.py results/evidence/evidence_bundle.b64
  python scripts/import_evidence_bundle.py results/evidence/trajectories-archive.tar.gz
  python scripts/import_evidence_bundle.py /tmp/evidence-bundle.tgz

Writes extracted files under results/evidence/ and optionally extracts
trajectories into trajectories/ for audit_wins.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import re
import shutil
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO / "results" / "evidence"
TRAJ_ARCHIVE = EVIDENCE_DIR / "trajectories-archive.tar.gz"

# Notebook export (2026-07-12) — see docs/BENCHMARK_EVIDENCE_PROVENANCE.md
EXPECTED_SHA256 = {
    "trajectories-archive.tar.gz": (
        "e8a7554546985a958dd0f4947eb6e8a7e771f58f681d1f8b51d258aa77e5c9c8"
    ),
    "metrics.jsonl": "d8616b9ea66f496ad556371390a615974c35e73709cdc4c2b9636603746b12e8",
    "holdout.jsonl": "e2e2bdbf3cfc3f8353450a39e0115d81de7f625f37e93d38912231cda5f86b51",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_b64(text: str) -> str:
    text = re.sub(r"root@.*$", "", text, flags=re.DOTALL)
    text = re.sub(r"</user_query>.*$", "", text, flags=re.DOTALL)
    text = re.sub(r"[^A-Za-z0-9+/=]", "", text)
    pad = (-len(text)) % 4
    if pad:
        text += "=" * pad
    return text


def fix_mangled_gzip_prefix(text: str) -> list[str]:
    """Chat paste sometimes mangles gzip base64 prefix H4sI -> /gsYn."""
    candidates = [text]
    if text.startswith("/gsYn/"):
        candidates.append("H4sIb" + text[len("/gsYn/b") :])
        candidates.append("H4sI" + text[len("/gsYn/") :])
    if text.startswith("/gsYn"):
        candidates.append("H4sI" + text[len("/gsYn") :])
        candidates.append(text[1:])
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def decode_b64(path: Path) -> bytes:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = clean_b64(raw)
    last_err: Exception | None = None
    for candidate in fix_mangled_gzip_prefix(cleaned):
        try:
            return base64.b64decode(candidate, validate=True)
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return base64.b64decode(cleaned)


def verify_gzip_tar(data: bytes) -> None:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.getmembers()


def extract_tar_bytes(data: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")


def extract_tar_file(path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:gz") as tar:
        tar.extractall(dest, filter="data")


def sync_notebook_metrics(bundle_dir: Path) -> None:
    for name in ("metrics.jsonl", "holdout.jsonl"):
        src = bundle_dir / "results" / name
        if not src.exists():
            src = bundle_dir / name
        if not src.exists():
            continue
        dest = REPO / "results" / name
        shutil.copy2(src, dest)
        print(f"Copied {src.relative_to(bundle_dir)} -> {dest}")
        expected = EXPECTED_SHA256.get(name)
        if expected:
            got = sha256_file(dest)
            if got != expected:
                print(
                    f"WARN: {name} SHA-256 {got} != notebook {expected}",
                    file=sys.stderr,
                )


def verify_archive(path: Path, label: str) -> bool:
    expected = EXPECTED_SHA256.get(label)
    if not expected:
        return True
    got = sha256_file(path)
    ok = got == expected
    print(f"SHA256 {label}: {got} {'OK' if ok else 'MISMATCH (expected ' + expected + ')'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help=".b64, .tar.gz, or evidence-bundle.tgz")
    parser.add_argument(
        "--extract-trajectories",
        action="store_true",
        help="Also extract trajectories/iter* from archive into repo root",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Do not check SHA-256 against notebook export hashes",
    )
    args = parser.parse_args()
    path: Path = args.input
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    if path.suffix == ".b64" or path.name.endswith(".b64"):
        try:
            data = decode_b64(path)
            verify_gzip_tar(data)
        except Exception as exc:
            print(
                "Failed to decode base64 as a valid gzip tarball.\n"
                "Chat paste often corrupts large base64 (H4sI -> /gsYn). "
                "Re-transfer via Jupyter Download or scp instead of paste.\n"
                f"Error: {exc}",
                file=sys.stderr,
            )
            return 1
        TRAJ_ARCHIVE.write_bytes(data)
        print(f"Wrote {TRAJ_ARCHIVE} ({len(data)} bytes)")
        extract_tar_bytes(data, EVIDENCE_DIR)
    elif path.suffixes[-2:] == [".tar", ".gz"] or path.name.endswith(".tar.gz"):
        shutil.copy2(path, TRAJ_ARCHIVE)
        extract_tar_file(path, EVIDENCE_DIR)
        print(f"Copied {path} -> {TRAJ_ARCHIVE}")
    elif path.name.endswith(".tgz") or path.suffix == ".tgz":
        extract_tar_file(path, EVIDENCE_DIR / "_bundle")
        bundle_root = EVIDENCE_DIR / "_bundle"
        inner = bundle_root / "results" / "evidence" / "trajectories-archive.tar.gz"
        if inner.exists():
            shutil.copy2(inner, TRAJ_ARCHIVE)
            print(f"Extracted inner archive -> {TRAJ_ARCHIVE}")
        sync_notebook_metrics(bundle_root)
    else:
        print(f"Unknown input type: {path}", file=sys.stderr)
        return 1

    if TRAJ_ARCHIVE.exists():
        print(f"SHA256 trajectories-archive: {sha256_file(TRAJ_ARCHIVE)}")
        if not args.skip_verify and not verify_archive(
            TRAJ_ARCHIVE, "trajectories-archive.tar.gz"
        ):
            return 1

    if args.extract_trajectories and TRAJ_ARCHIVE.exists():
        traj_root = EVIDENCE_DIR / "trajectories"
        if not traj_root.exists():
            # Inner archive may list trajectories/iter0/... at top level
            with tarfile.open(TRAJ_ARCHIVE, "r:gz") as tar:
                tar.extractall(EVIDENCE_DIR, filter="data")
        traj_root = EVIDENCE_DIR / "trajectories"
        if traj_root.exists():
            for item in traj_root.iterdir():
                dest = REPO / "trajectories" / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            print("Extracted trajectories/ to repo root for audit_wins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
