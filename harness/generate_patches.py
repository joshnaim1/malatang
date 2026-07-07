"""Regenerate benchmark bug patches from git diffs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRAINING_MANIFEST = REPO / "benchmark" / "manifest.json"
HOLDOUT_MANIFEST = REPO / "benchmark" / "holdout" / "manifest.json"

Edit = tuple[Path, str, str]

TRAINING_BUGS: dict[str, list[Edit]] = {
    "syntax-001": [(REPO / "src/App.jsx", "    </main>", "    </main")],
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
    "syntax-005": [
        (
            REPO / "src/App.jsx",
            "{formatCents(line.total)}",
            "{formatCents(line.total}",
        ),
    ],
    "syntax-006": [
        (
            REPO / "src/main.jsx",
            "  </StrictMode>,",
            "  </StrictMode",
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
    "offbyone-004": [
        (
            REPO / "lib/stats.js",
            "  return values.reduce((acc, value) => acc + value, 0);",
            "  return values.reduce((acc, value) => acc + value, 1);",
        ),
    ],
    "offbyone-005": [
        (
            REPO / "lib/stats.js",
            "  const end = start + pageSize;",
            "  const end = start + pageSize - 1;",
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
        (REPO / "lib/stats.js", "    return null;", "    return 0;"),
    ],
    "null-003": [
        (
            REPO / "lib/format.js",
            "  return lines.reduce((acc, line) => acc + line.total, 0);",
            "  return lines.reduce((acc, line) => acc + line.total + line.tax, 0);",
        ),
    ],
    "null-004": [
        (
            REPO / "lib/format.js",
            "  if (cents == null) {\n    return \"$0.00\";\n  }\n",
            "",
        ),
    ],
    "null-005": [
        (
            REPO / "lib/stats.js",
            "  if (values == null) {\n    return null;\n  }\n",
            "",
        ),
    ],
    "api-001": [
        (
            REPO / "lib/currency.js",
            "  return usdFormatter.format(cents / 100);",
            "  return usdFormatter.format(cents);",
        ),
    ],
    "api-002": [
        (
            REPO / "lib/currency.js",
            '  return formatMoney(cents).replace(/[^\\d.]/g, "");',
            "  return usdFormatter\n    .formatToParts(cents / 100)\n    .filter((part) => part.type === \"integer\")\n    .map((part) => part.value)\n    .join(\"\");",
        ),
    ],
    "api-003": [
        (
            REPO / "lib/currency.js",
            "  return usdFormatter.resolvedOptions().currency;",
            "  return usdFormatter.resolvedOptions().style;",
        ),
    ],
    "api-004": [
        (
            REPO / "lib/currency.js",
            '  const parts = usdFormatter.formatToParts(amount);\n  const currencyPart = parts.find((part) => part.type === "currency");\n  return currencyPart?.value ?? "";',
            "  return usdFormatter.format(amount);",
        ),
    ],
    "api-005": [
        (
            REPO / "lib/currency.js",
            '  const integer = parts.find((part) => part.type === "integer");',
            '  const integer = parts.find((part) => part.type === "currency");',
        ),
    ],
    "async-001": [
        (
            REPO / "lib/asyncCart.js",
            "  const totals = await Promise.all(",
            "  const totals = Promise.all(",
        ),
    ],
    "async-002": [
        (
            REPO / "lib/asyncCart.js",
            "  const results = await Promise.all(checks);",
            "  const results = Promise.all(checks);",
        ),
    ],
    "async-003": [
        (
            REPO / "lib/asyncCart.js",
            "export async function loadCartTotal(lines) {",
            "export function loadCartTotal(lines) {",
        ),
    ],
    "async-004": [
        (
            REPO / "lib/asyncCart.js",
            '  return results.every((label) => label !== "Unknown");',
            "  return true;",
        ),
    ],
}

HOLDOUT_BUGS: dict[str, list[Edit]] = {
    "holdout-001": [
        (
            REPO / "lib/currency.js",
            "  return usdFormatter.format(cents / 100);\n}\n\n/** Compact display",
            "  return usdFormatter.format(cents / 100);\n\n/** Compact display",
        ),
    ],
    "holdout-002": [
        (
            REPO / "lib/asyncCart.js",
            "  return totals.reduce((acc, value) => acc + value, 0);",
            "  return totals.slice(1).reduce((acc, value) => acc + value, 0);",
        ),
    ],
    "holdout-003": [
        (
            REPO / "lib/currency.js",
            "  if (cents == null) {\n    return usdFormatter.format(0);\n  }\n",
            "",
        ),
    ],
    "holdout-004": [
        (
            REPO / "lib/currency.js",
            '  currency: "USD",',
            '  currency: "USDD",',
        ),
    ],
    "holdout-005": [
        (
            REPO / "lib/asyncCart.js",
            "  return fetchSpiceLabel(key);",
            "  return key;",
        ),
    ],
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def write_patch(path: Path, edits: list[Edit], description: str = "") -> None:
    for file_path, old, new in edits:
        text = file_path.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"{path.name}: snippet not found in {file_path}")
        file_path.write_text(text.replace(old, new, 1), encoding="utf-8")

    diff = _git("diff")
    if diff.returncode != 0:
        raise RuntimeError(diff.stderr or "git diff failed")

    restore = _git("checkout", "--", ".")
    if restore.returncode != 0:
        raise RuntimeError(restore.stderr or "git checkout failed")

    header = f"# {description}\n" if description else ""
    path.write_text((header + diff.stdout).replace("\r\n", "\n"), encoding="utf-8")


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


def load_descriptions(manifest_path: Path) -> dict[str, str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["id"]: entry["description"] for entry in data["bugs"]}


def generate_set(
    bugs: dict[str, list[Edit]],
    descriptions: dict[str, str],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for bug_id, edits in bugs.items():
        write_patch(output_dir / f"{bug_id}.patch", edits, descriptions[bug_id])


def main() -> None:
    training_descriptions = load_descriptions(TRAINING_MANIFEST)
    holdout_descriptions = load_descriptions(HOLDOUT_MANIFEST)

    generate_set(TRAINING_BUGS, training_descriptions, REPO / "benchmark" / "bugs")
    generate_set(HOLDOUT_BUGS, holdout_descriptions, REPO / "benchmark" / "holdout")

    bug_patch = (REPO / "benchmark" / "bugs" / "syntax-001.patch").read_text(
        encoding="utf-8"
    )
    fix_body = invert_patch(
        "\n".join(line for line in bug_patch.splitlines() if not line.startswith("#"))
        + "\n"
    )
    fixes_dir = REPO / "benchmark" / "fixes"
    fixes_dir.mkdir(parents=True, exist_ok=True)
    (fixes_dir / "syntax-001.patch").write_text(
        f"# {training_descriptions['syntax-001']} (fix)\n{fix_body}",
        encoding="utf-8",
    )
    print("Regenerated 25 training + 5 hold-out bug patches.")


if __name__ == "__main__":
    main()
