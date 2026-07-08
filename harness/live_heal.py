"""Live-heal demo — the Judge-verify half of Beat 1 (SOW section 3).

Narrates one heal cycle: the app is broken by a seeded bug (sandbox gate goes
red), a Creator backend proposes a fix, and the real Judge sandbox-verifies it
green. This is the deterministic verification half Person B owns; the visible
page break / auto-deploy theater is layered on top for the recording.

    python -m harness.live_heal --bug-id syntax-001 --creator mock
"""

from __future__ import annotations

import argparse
import sys

from harness.benchmark_io import TRAINING_DIR, load_bug_patch, load_training_bugs
from harness.creator_backend import get_backend
from harness.judge import verify_bug_state, verify_mutation


def _find_bug(bug_id: str) -> dict[str, str]:
    for bug in load_training_bugs():
        if bug["id"] == bug_id:
            return bug
    raise SystemExit(f"bug_id not found in training manifest: {bug_id}")


def live_heal(bug_id: str, creator: str) -> int:
    bug = _find_bug(bug_id)
    bug_patch = load_bug_patch(TRAINING_DIR, bug)

    print(f"1. Injecting bug {bug_id} [{bug.get('class')}] — {bug.get('description', '')}")
    broken = verify_bug_state(bug_patch)
    broken_ok = not broken.build_passed or not broken.tests_passed
    state = "BROKEN (build/tests red)" if broken_ok else "still green?!"
    print(f"   App is {state} — build_passed={broken.build_passed} tests_passed={broken.tests_passed}")
    if not broken_ok:
        print("   Bug did not break the app; aborting heal demo.")
        return 1

    print(f"2. Creator ({creator}) proposing a fix...")
    backend = get_backend(creator)
    try:
        failing_output = (broken.build_output + "\n" + broken.test_output).strip()
        mutation = backend.create_mutation(
            bug,
            iteration=0,
            playbook_version="v0",
            attempt=1,
            failing_output=failing_output,
        )
    finally:
        backend.close()
    print(f"   Proposed: {mutation['mutation']['reasoning']}")

    print("3. Judge sandbox-verifying the fix...")
    verdict = verify_mutation(mutation, bug_patch)
    print(
        f"   build_passed={verdict['build_passed']} "
        f"tests_passed={verdict['tests_passed']} "
        f"accepted={verdict['accepted']} ({verdict['wall_time_s']}s)"
    )

    if verdict["accepted"]:
        print(f"4. HEALED — {bug_id} verified green. Page is back.")
        return 0
    print(f"4. NOT healed — {creator} did not produce a passing fix for {bug_id}.")
    return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Malatang live-heal demo (Judge half)")
    parser.add_argument("--bug-id", default="syntax-001", help="seeded bug to heal")
    parser.add_argument(
        "--creator",
        choices=["fake", "mock", "live"],
        default="mock",
        help="Creator backend that proposes the fix (default: mock)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return live_heal(args.bug_id, args.creator)


if __name__ == "__main__":
    sys.exit(main())
