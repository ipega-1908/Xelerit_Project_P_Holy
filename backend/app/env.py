import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a local .env file without overriding existing env vars."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        # Keep explicit shell or container environment variables higher priority.
        os.environ.setdefault(key, value)


def load_default_env_files() -> None:
    """Load optional local .env files from backend/ and repository root."""
    backend_dir = Path(__file__).resolve().parent.parent
    repo_root = backend_dir.parent
    load_env_file(backend_dir / ".env")
    load_env_file(repo_root / ".env")
