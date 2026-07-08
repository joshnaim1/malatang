"""Build step 3: run the reflection step to rewrite the playbook.

    trajectories/iterN/  ->  Fireworks reflection  ->  playbook/vN+1.md

Usage:
    python -m scripts.reflect --iteration 0 --dry-run   # no API call
    python -m scripts.reflect --iteration 0             # calls Fireworks
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from creator.reflection import load_iteration_trajectories, reflect


async def main() -> int:
    parser = argparse.ArgumentParser(description="Reflection: rewrite playbook")
    parser.add_argument("--iteration", type=int, default=0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build prompt + write derived playbook without calling Fireworks",
    )
    args = parser.parse_args()

    traj = load_iteration_trajectories(args.iteration)
    print(
        f"Iteration {args.iteration}: {len(traj.wins)} wins, "
        f"{len(traj.failures)} failures ({traj.total} attempts)"
    )
    if traj.total == 0:
        print("No trajectories found — run scripts.creator_e2e first.")
        return 1

    mode = "DRY-RUN (no Fireworks call)" if args.dry_run else "LIVE (Fireworks)"
    print(f"Mode: {mode}")

    next_version, out_path = await reflect(args.iteration, dry_run=args.dry_run)
    print(f"Wrote {next_version} -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
