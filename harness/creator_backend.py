"""Creator backends for the Runner — the fake→real Creator swap (SOW section 13).

The Runner is Person B's; it calls whichever backend is selected and hands the
returned mutation to the real Judge. Three backends:

- ``fake``  : the self-contained stub in ``harness/fake_creator.py`` (no external
              deps, one canned true positive on syntax-001). Default.
- ``mock``  : Person A's real Creator pipeline stages with the mock fix stage —
              contract-valid mutations end-to-end, no GPU. Proves the seam.
- ``live``  : Person A's Creator against the MI300X vLLM endpoint. Requires the
              droplet up and the vLLM env vars set; fails loud otherwise.

Only the Judge verdict decides pass/fail; a backend only produces the mutation.
"""

from __future__ import annotations

from typing import Any, Protocol


class CreatorBackend(Protocol):
    name: str

    def prepare_iteration(self, playbook_version: str) -> str:
        """Load iteration state and return the version actually loaded."""
        ...

    def create_mutation(
        self,
        bug: dict[str, str],
        *,
        iteration: int,
        playbook_version: str,
        attempt: int,
        failing_output: str | None = None,
    ) -> dict[str, Any]: ...

    def close(self) -> None: ...


class FakeCreatorBackend:
    """Self-contained stub; no Creator-half dependency."""

    name = "fake"

    def prepare_iteration(self, playbook_version: str) -> str:
        return playbook_version

    def create_mutation(
        self,
        bug: dict[str, str],
        *,
        iteration: int,
        playbook_version: str,
        attempt: int,
        failing_output: str | None = None,
    ) -> dict[str, Any]:
        from harness.fake_creator import create_mutation

        return create_mutation(
            bug["id"],
            iteration=iteration,
            playbook_version=playbook_version,
            attempt=attempt,
            use_canned_fix=(attempt == 1),
        )

    def close(self) -> None:  # noqa: D401 - nothing to release
        pass


class MockCreatorBackend:
    """Person A's pipeline stages with the mock (no-GPU) fix stage."""

    name = "mock"

    def prepare_iteration(self, playbook_version: str) -> str:
        return playbook_version

    def create_mutation(
        self,
        bug: dict[str, str],
        *,
        iteration: int,
        playbook_version: str,
        attempt: int,
        failing_output: str | None = None,
    ) -> dict[str, Any]:
        from creator.bug_context import build_bug_context
        from creator.mock_creator import generate_fix_mock
        from creator.observer import observe
        from creator.pipeline import build_mutation

        ctx = build_bug_context(bug["id"], failing_output=failing_output)
        obs = observe(ctx)
        fix = generate_fix_mock(obs)
        return build_mutation(
            obs,
            fix,
            iteration=iteration,
            playbook_version=playbook_version,
            attempt=attempt,
            model_label="mock-creator",
        )

    def close(self) -> None:
        pass


class LiveCreatorBackend:
    """Person A's Creator against the live vLLM endpoint (MI300X)."""

    name = "live"

    def __init__(self) -> None:
        import asyncio

        from openai import AsyncOpenAI

        from creator import config as creator_config
        self._asyncio = asyncio
        self._loop = asyncio.new_event_loop()
        self._model = creator_config.creator_model()
        self._temperature = creator_config.benchmark_temperature()
        self._playbook_version: str | None = None
        self._playbook_text: str | None = None
        self._client = AsyncOpenAI(
            base_url=creator_config.vllm_base_url(),
            api_key=creator_config.vllm_api_key(),
        )

    def prepare_iteration(self, playbook_version: str) -> str:
        """Load the exact requested playbook once per benchmark iteration."""
        from creator import playbook

        self._playbook_text = playbook.load_playbook(playbook_version)
        self._playbook_version = playbook_version
        return self._playbook_version

    def create_mutation(
        self,
        bug: dict[str, str],
        *,
        iteration: int,
        playbook_version: str,
        attempt: int,
        failing_output: str | None = None,
    ) -> dict[str, Any]:
        from creator.bug_context import build_bug_context
        from creator.pipeline import run_attempt

        if self._playbook_version != playbook_version or self._playbook_text is None:
            self.prepare_iteration(playbook_version)
        assert self._playbook_version is not None
        assert self._playbook_text is not None
        ctx = build_bug_context(bug["id"], failing_output=failing_output)
        return self._loop.run_until_complete(
            run_attempt(
                ctx,
                client=self._client,
                model=self._model,
                model_label=self._model,
                playbook_text=self._playbook_text,
                playbook_version=self._playbook_version,
                iteration=iteration,
                attempt=attempt,
                temperature=self._temperature,
            )
        )

    def close(self) -> None:
        try:
            self._loop.run_until_complete(self._client.close())
        finally:
            self._loop.close()


_BACKENDS = {
    "fake": FakeCreatorBackend,
    "mock": MockCreatorBackend,
    "live": LiveCreatorBackend,
}


def get_backend(name: str) -> CreatorBackend:
    if name not in _BACKENDS:
        raise ValueError(
            f"unknown creator backend {name!r}; choose from {sorted(_BACKENDS)}"
        )
    return _BACKENDS[name]()
