"""One-off helper to regenerate benchmark bug patches from git diffs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "benchmark" / "manifest.json"


def write_patch(path: Path, edits: list[tuple[Path, str, str]], description: str = "") -> None:
    for file_path, old, new in edits:
        text = file_path.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"{file_path}: old snippet not found")
        file_path.write_text(text.replace(old, new, 1), encoding="utf-8")

    diff = subprocess.run(
        ["git", "diff"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    subprocess.run(["git", "checkout", "--", "."], cwd=REPO, check=True)
    header = f"# {description}\n" if description else ""
    path.write_text((header + diff).replace("\r\n", "\n"), encoding="utf-8")


BUGS = {
    "syntax-001": [
        (REPO / "src/App.jsx", "    </main>", "    </main"),
    ],
    "syntax-002": [
        (
            REPO / "src/App.jsx",
            "          <li key={line.name}>",
            "          <li key={line.name}",
        ),
    ],
    "syntax-003": [
        (
            REPO / "lib/stats.js",
            "  return values.reduce((acc, value) => acc + value, 0);\n}",
            "  return values.reduce((acc, value) => acc + value, 0);\n",
        ),
    ],
    "syntax-004": [
        (
            REPO / "lib/format.js",
            '  return `$${dollars.toFixed(2)}`;',
            "  return `$${dollars.toFixed(2}`;",
        ),
    ],
    "offbyone-001": [
        (
            REPO / "lib/stats.js",
            "  const end = start + pageSize;",
            "  const end = start + pageSize + 1;",
        ),
    ],
    "offbyone-002": [
        (
            REPO / "lib/stats.js",
            "  for (let i = 0; i < items.length; i += 1) {\n    if (items[i]?.qty >= minQty) {",
            "  for (let i = 0; i <= items.length; i += 1) {\n    if (items[i].qty >= minQty) {",
        ),
    ],
    "offbyone-003": [
        (
            REPO / "lib/stats.js",
            "  const start = page * pageSize;",
            "  const start = page * pageSize + 1;",
        ),
    ],
    "null-001": [
        (
            REPO / "lib/format.js",
            '  const spice = spiceLevel?.label ?? "mild";',
            '  const spice = spiceLevel.label ?? "mild";',
        ),
    ],
    "null-002": [
        (
            REPO / "lib/stats.js",
            "    return null;",
            "    return 0;",
        ),
    ],
    "null-003": [
        (
            REPO / "lib/format.js",
            "  return lines.reduce((acc, line) => acc + line.total, 0);",
            "  return lines.reduce((acc, line) => acc + line.total + line.tax, 0);",
        ),
    ],
}


def invert_patch(patch_text: str) -> str:
    inverted: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            inverted.append("+" + line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            inverted.append("-" + line[1:])
        else:
            inverted.append(line)
    return "\n".join(inverted) + "\n"


def main() -> None:
    bugs_dir = REPO / "benchmark" / "bugs"
    fixes_dir = REPO / "benchmark" / "fixes"
    bugs_dir.mkdir(parents=True, exist_ok=True)
    fixes_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    descriptions = {entry["id"]: entry["description"] for entry in manifest["bugs"]}

    for bug_id, edits in BUGS.items():
        write_patch(
            bugs_dir / f"{bug_id}.patch",
            edits,
            descriptions[bug_id],
        )

    bug_patch = (bugs_dir / "syntax-001.patch").read_text(encoding="utf-8")
    fix_body = invert_patch("\n".join(line for line in bug_patch.splitlines() if not line.startswith("#")) + "\n")
    (fixes_dir / "syntax-001.patch").write_text(
        f"# {descriptions['syntax-001']} (fix)\n{fix_body}",
        encoding="utf-8",
    )
    print("Regenerated bug and fix patches.")


if __name__ == "__main__":
    main()
