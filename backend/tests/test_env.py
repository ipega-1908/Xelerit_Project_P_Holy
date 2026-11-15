import os
from pathlib import Path

import pytest

from app.env import load_env_file


def test_load_env_file_sets_missing_vars_and_strips_quotes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_GEMINI_KEY", raising=False)
    monkeypatch.setenv("EXISTING_KEY", "from-shell")

    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment line\n\nTEST_GEMINI_KEY=\"abc-123\"\nEXISTING_KEY='from-file'\nINVALID_LINE\n",
        encoding="utf-8",
    )

    load_env_file(env_path)

    assert os.getenv("TEST_GEMINI_KEY") == "abc-123"
    assert os.getenv("EXISTING_KEY") == "from-shell"


def test_load_env_file_ignores_missing_file(tmp_path: Path) -> None:
    load_env_file(tmp_path / "does-not-exist.env")
