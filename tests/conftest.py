"""Shared test kit: everything here runs with NO model and NO Modal ($0).

Run:  uv run pytest
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import agents_base  # noqa: E402


@pytest.fixture
def fake_model(monkeypatch):
    """Install a scripted model. Pass a callable(prompt) -> dict move; the
    fixture wraps it in JSON. Restores the real router after the test."""

    def install(script):
        def think(prompt: str, max_new_tokens: int = 0) -> str:
            return json.dumps(script(prompt))

        monkeypatch.setattr(agents_base.router, "think", think)

    return install


def make_finding(**over) -> dict:
    f = {
        "finding_id": "f-AI-0001-pol-1",
        "inspector": "policy_compliance",
        "control_id": "POL-01",
        "severity": "high",
        "plain": "Customer data goes to an outside company.",
        "evidence": "third_party set",
        "remediation": "Use the in-house lane.",
        "status": "open",
    }
    f.update(over)
    return f
